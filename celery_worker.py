# celery_worker.py - Simple Image Processing Worker
from celery import Celery
from PIL import Image
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis URL for your EC2 instance
REDIS_URL = os.getenv("REDIS_URL", "redis://172.31.42.185:6379")

# Create Celery app
celery_app = Celery(
    'simple_image_processor',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['celery_worker']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max
    worker_prefetch_multiplier=1,
    result_expires=3600  # 1 hour
)

@celery_app.task(bind=True)
def process_image_task(self, file_path, file_id):
    """
    Process uploaded image: resize to max 800px and optimize
    """
    try:
        logger.info(f"Starting image processing for file_id: {file_id}")
        logger.info(f"Processing file: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Open and process the image
        with Image.open(file_path) as img:
            logger.info(f"Original image: {img.size}, mode: {img.mode}, format: {img.format}")
            
            # Store original info
            original_size = img.size
            original_mode = img.mode
            
            # Convert to RGB if needed (for JPEG output)
            if img.mode in ('RGBA', 'P', 'LA'):
                # Create white background for transparent images
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
                logger.info(f"Converted {original_mode} to RGB")
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                logger.info(f"Converted {original_mode} to RGB")
            
            # Resize image (max dimension 800px, maintain aspect ratio)
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            new_size = img.size
            
            logger.info(f"Resized from {original_size} to {new_size}")
            
            # Create processed directory if it doesn't exist
            os.makedirs("processed", exist_ok=True)
            
            # Save processed image
            output_path = os.path.join("processed", f"{file_id}_processed.jpg")
            img.save(output_path, "JPEG", quality=85, optimize=True)
            
            # Get file sizes
            original_size_bytes = os.path.getsize(file_path)
            processed_size_bytes = os.path.getsize(output_path)
            
            # Calculate compression
            compression_ratio = ((original_size_bytes - processed_size_bytes) / original_size_bytes) * 100
            
            result = {
                "status": "completed",
                "file_id": file_id,
                "original_dimensions": original_size,
                "processed_dimensions": new_size,
                "original_size_mb": round(original_size_bytes / (1024 * 1024), 2),
                "processed_size_mb": round(processed_size_bytes / (1024 * 1024), 2),
                "compression_ratio": round(compression_ratio, 1),
                "output_path": output_path,
                "original_mode": original_mode,
                "message": "Image resized and optimized successfully"
            }
            
            logger.info(f"Processing completed: {result}")
            return result
            
    except Exception as e:
        error_msg = f"Error processing image {file_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Return error info
        return {
            "status": "error",
            "file_id": file_id,
            "message": error_msg,
            "error": str(e)
        }

@celery_app.task
def test_task(message):
    """Simple test task to verify worker connectivity"""
    logger.info(f"Test task executed with message: {message}")
    return f"Test completed: {message}"

# Export the app for importing in main.py
app = celery_app

if __name__ == "__main__":
    # Start worker directly
    celery_app.start()