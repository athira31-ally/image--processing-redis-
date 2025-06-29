# main.py - Simple Image Processing API
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os
import uuid
from celery_worker import process_image_task, celery_app
from typing import Dict
import redis
import json

app = FastAPI(title="Simple Image Processor", version="1.0.0")

# Redis connection for task storage
REDIS_URL = os.getenv("REDIS_URL", "redis://172.31.42.185:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Create directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("processed", exist_ok=True)

@app.get("/")
def home():
    return {
        "message": "Simple Image Processing API - Upload images to resize and optimize them!",
        "endpoints": {
            "upload": "POST /upload-image/ - Upload image for processing",
            "status": "GET /status/{task_id} - Check processing status", 
            "download": "GET /download/{file_id} - Download processed image",
            "tasks": "GET /tasks/ - List all tasks"
        },
        "processing": "Resize to max 800px, optimize quality, convert to JPEG"
    }

@app.post("/upload-image/")
async def upload_image(file: UploadFile = File(...)):
    """
    STEP 1: Upload an image and start background processing
    """
    # Check if file is an image
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    original_filename = f"{file_id}_original.{file_extension}"
    
    # Save uploaded file
    file_path = os.path.join("uploads", original_filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Start background processing task
    task = process_image_task.delay(file_path, file_id)
    
    # Store task info in Redis
    task_info = {
        "file_id": file_id,
        "original_name": file.filename,
        "status": "processing",
        "file_path": file_path,
        "file_size_bytes": len(content)
    }
    redis_client.set(f"task:{task.id}", json.dumps(task_info), ex=3600)  # Expire in 1 hour
    
    return {
        "message": "Image uploaded successfully! Processing started.",
        "task_id": str(task.id),
        "file_id": file_id,
        "original_filename": file.filename,
        "status": "processing",
        "file_size_mb": round(len(content) / (1024 * 1024), 2)
    }

@app.get("/status/{task_id}")
def check_status(task_id: str):
    """
    STEP 2: Check if image processing is complete
    """
    task_data = redis_client.get(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = json.loads(task_data)
    
    # Get task result from Celery
    task_result = celery_app.AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Image is being processed...",
            "file_id": task_info["file_id"]
        }
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "Image processed successfully!",
            "file_id": task_info["file_id"],
            "download_url": f"/download/{task_info['file_id']}",
            "processing_info": result
        }
    elif task_result.state == 'FAILURE':
        return {
            "task_id": task_id,
            "status": "failed",
            "message": "Image processing failed",
            "file_id": task_info["file_id"],
            "error": str(task_result.info)
        }
    else:
        return {
            "task_id": task_id,
            "status": task_result.state,
            "message": f"Task is {task_result.state}",
            "file_id": task_info["file_id"]
        }

@app.get("/download/{file_id}")
def download_processed_image(file_id: str):
    """
    STEP 3: Download the processed image
    """
    processed_file = os.path.join("processed", f"{file_id}_processed.jpg")
    
    if not os.path.exists(processed_file):
        raise HTTPException(status_code=404, detail="Processed image not found. Make sure processing is completed.")
    
    return FileResponse(
        processed_file,
        media_type='image/jpeg',
        filename=f"processed_{file_id}.jpg"
    )

@app.get("/tasks/")
def list_all_tasks():
    """
    See all processing tasks
    """
    # Get all task keys from Redis
    task_keys = redis_client.keys("task:*")
    result = {}
    
    for key in task_keys:
        task_id = key.split(":", 1)[1]
        try:
            task_data = redis_client.get(key)
            task_info = json.loads(task_data)
            
            # Get current status from Celery
            task_result = celery_app.AsyncResult(task_id)
            
            result[task_id] = {
                **task_info,
                "current_status": task_result.state,
                "has_result": task_result.result is not None
            }
        except Exception as e:
            result[task_id] = {
                "error": str(e),
                "current_status": "unknown"
            }
    
    return {"tasks": result, "total_tasks": len(result)}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        redis_status = "healthy"
    except:
        redis_status = "error"
    
    return {
        "status": "healthy",
        "redis": redis_status,
        "celery": "enabled",
        "processing": "resize & optimize"
    }