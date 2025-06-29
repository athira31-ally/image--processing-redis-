from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import redis
import os
import uuid
import json
from datetime import datetime
from PIL import Image
import io
import base64
from celery import Celery
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Image Processing System",
    description="A high-performance image processing API with Redis caching and Celery",
    version="1.0.0"
)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    redis_available = True
    logger.info("✅ Redis connected successfully")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    redis_available = False

# Celery setup
celery_app = Celery(
    'image_processor',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['main']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'main.process_image_task': 'image_processing'
    }
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Image Processing System with Celery is running",
        "status": "healthy",
        "redis_available": redis_available,
        "celery_configured": True
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    uptime = datetime.now().isoformat()
    
    # Test Redis connection
    redis_status = "connected" if redis_available else "disconnected"
    if redis_available:
        try:
            redis_client.ping()
            redis_status = "connected"
        except:
            redis_status = "disconnected"
    
    # Test Celery worker availability
    celery_status = "unknown"
    active_workers = 0
    if redis_available:
        try:
            inspect = celery_app.control.inspect()
            active_workers_dict = inspect.active()
            active_workers = len(active_workers_dict) if active_workers_dict else 0
            celery_status = "workers_available" if active_workers > 0 else "no_workers"
        except Exception as e:
            celery_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "services": {
            "api": "ready",
            "redis": redis_status,
            "celery": celery_status,
            "active_workers": active_workers
        },
        "uptime": uptime
    }

@app.post("/upload-image/")
async def upload_image(file: UploadFile = File(...)):
    """Upload and queue image for processing"""
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    if not redis_available:
        raise HTTPException(status_code=503, detail="Redis not available - cannot process images")
    
    # Generate unique ID for this upload
    upload_id = str(uuid.uuid4())
    
    try:
        # Read file contents
        contents = await file.read()
        
        # Basic image validation
        image = Image.open(io.BytesIO(contents))
        
        # Initial image info
        image_info = {
            "upload_id": upload_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(contents),
            "dimensions": {
                "width": image.width,
                "height": image.height
            },
            "format": image.format,
            "mode": image.mode,
            "upload_time": datetime.now().isoformat(),
            "status": "queued",
            "processing_type": "asynchronous"
        }
        
        # Store original image data in Redis temporarily
        image_b64 = base64.b64encode(contents).decode()
        redis_client.setex(f"image_data:{upload_id}", 3600, image_b64)
        
        # Store initial metadata
        redis_client.setex(
            f"image_metadata:{upload_id}", 
            3600,
            json.dumps(image_info)
        )
        
        # Queue processing task
        task_result = process_image_task.delay(upload_id, image_info)
        
        # Update with task info
        image_info["task_id"] = task_result.id
        image_info["task_status"] = "PENDING"
        
        redis_client.setex(
            f"image_metadata:{upload_id}", 
            3600,
            json.dumps(image_info)
        )
        
        logger.info(f"✅ Image {upload_id} queued for processing, task: {task_result.id}")
        
        return JSONResponse(
            status_code=202,  # Accepted for processing
            content={
                "message": "Image queued for processing",
                "data": image_info,
                "check_status_url": f"/status/{upload_id}"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Image upload failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Image upload failed: {str(e)}"
        )

@app.get("/status/{upload_id}")
async def get_processing_status(upload_id: str):
    """Get processing status of an image"""
    
    if not redis_available:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    try:
        # Get metadata from Redis
        metadata = redis_client.get(f"image_metadata:{upload_id}")
        if not metadata:
            raise HTTPException(status_code=404, detail="Upload ID not found")
        
        data = json.loads(metadata)
        
        # Check task status if task was queued
        if "task_id" in data:
            try:
                task_result = celery_app.AsyncResult(data["task_id"])
                data["task_status"] = task_result.status
                
                if task_result.ready():
                    if task_result.successful():
                        data["task_result"] = task_result.result
                    else:
                        data["task_error"] = str(task_result.result)
                
            except Exception as e:
                data["task_status"] = "ERROR"
                data["task_error"] = str(e)
        
        return {"status": "found", "data": data}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")

@app.get("/image/{upload_id}")
async def get_image_info(upload_id: str):
    """Get information about a processed image"""
    
    if not redis_available:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    try:
        metadata = redis_client.get(f"image_metadata:{upload_id}")
        if not metadata:
            raise HTTPException(status_code=404, detail="Image not found")
        
        return JSONResponse(content=json.loads(metadata))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve image info: {str(e)}")

@app.get("/image/{upload_id}/thumbnail")
async def get_image_thumbnail(upload_id: str):
    """Get thumbnail of a processed image"""
    
    if not redis_available:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    try:
        thumbnail_b64 = redis_client.get(f"image_thumbnail:{upload_id}")
        if not thumbnail_b64:
            raise HTTPException(status_code=404, detail="Thumbnail not found or not yet processed")
        
        return {
            "upload_id": upload_id,
            "thumbnail_base64": thumbnail_b64,
            "format": "JPEG"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve thumbnail: {str(e)}")

@app.get("/workers")
async def get_worker_status():
    """Get Celery worker status"""
    if not redis_available:
        return {"error": "Redis not available"}
    
    try:
        inspect = celery_app.control.inspect()
        
        return {
            "active_workers": inspect.active(),
            "available_workers": inspect.stats(),
            "registered_tasks": inspect.registered()
        }
    except Exception as e:
        return {"error": str(e)}

# Celery task for image processing
@celery_app.task
def process_image_task(upload_id: str, image_info: dict):
    """Background task for image processing"""
    try:
        logger.info(f"🔄 Starting image processing for {upload_id}")
        
        # Get image data from Redis
        image_data_b64 = redis_client.get(f"image_data:{upload_id}")
        if not image_data_b64:
            raise Exception("Image data not found in Redis")
        
        # Decode image
        image_data = base64.b64decode(image_data_b64)
        image = Image.open(io.BytesIO(image_data))
        
        # Update status to processing
        image_info["status"] = "processing"
        image_info["processing_started"] = datetime.now().isoformat()
        redis_client.setex(f"image_metadata:{upload_id}", 3600, json.dumps(image_info))
        
        # Create thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail((200, 200))
        thumb_buffer = io.BytesIO()
        thumbnail.save(thumb_buffer, format='JPEG')
        thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()
        
        # Store thumbnail
        redis_client.setex(f"image_thumbnail:{upload_id}", 3600, thumb_b64)
        
        # Simulate additional processing
        import time
        time.sleep(3)  # Simulate processing time
        
        # Create processed version (example: convert to grayscale)
        processed_image = image.convert('L')  # Convert to grayscale
        processed_buffer = io.BytesIO()
        processed_image.save(processed_buffer, format='JPEG')
        processed_b64 = base64.b64encode(processed_buffer.getvalue()).decode()
        
        # Store processed image
        redis_client.setex(f"image_processed:{upload_id}", 3600, processed_b64)
        
        # Update final status
        image_info.update({
            "status": "completed",
            "processing_completed": datetime.now().isoformat(),
            "thumbnail_available": True,
            "processed_available": True,
            "processing_effects": ["grayscale_conversion", "thumbnail_generation"]
        })
        
        redis_client.setex(f"image_metadata:{upload_id}", 3600, json.dumps(image_info))
        
        # Clean up original image data
        redis_client.delete(f"image_data:{upload_id}")
        
        logger.info(f"✅ Image processing completed for {upload_id}")
        
        return {
            "status": "completed",
            "upload_id": upload_id,
            "processing_time": "~3 seconds",
            "effects_applied": ["grayscale", "thumbnail"]
        }
        
    except Exception as e:
        logger.error(f"❌ Image processing failed for {upload_id}: {e}")
        
        # Update status to failed
        image_info["status"] = "failed"
        image_info["error"] = str(e)
        image_info["failed_at"] = datetime.now().isoformat()
        redis_client.setex(f"image_metadata:{upload_id}", 3600, json.dumps(image_info))
        
        return {"status": "failed", "error": str(e), "upload_id": upload_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
