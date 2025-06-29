#!/bin/bash

# Start Celery worker in background
celery -A celery_worker worker --loglevel=info --detach

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000
