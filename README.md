# Image Processing System

A high-performance image processing API built with FastAPI and Redis, designed for AWS ECS deployment.

## Features

- 🚀 **FastAPI** - High-performance async web framework
- 📦 **Redis Integration** - Caching and job management
- 🖼️ **Image Processing** - Resize, blur, sharpen, filters, and more
- ⚡ **Background Jobs** - Non-blocking image processing
- 🐳 **Docker Ready** - Containerized for easy deployment
- ☁️ **AWS ECS Compatible** - Production-ready for cloud deployment

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the application:**
   ```bash
   ./start.sh
   ```

3. **Test the API:**
   ```bash
   python test_api.py
   ```

### Docker Development

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

2. **Access the API:**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## API Endpoints

### Core Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /upload` - Upload an image
- `POST /process/{file_id}` - Process an image
- `GET /status/{processing_id}` - Check processing status
- `GET /download/{processing_id}` - Download processed image
- `GET /list` - List uploaded images

### Image Operations

- **resize** - Resize image (width, height)
- **blur** - Apply Gaussian blur (intensity)
- **sharpen** - Sharpen image (intensity)
- **grayscale** - Convert to grayscale
- **sepia** - Apply sepia tone (intensity)
- **brightness** - Adjust brightness (intensity)
- **contrast** - Adjust contrast (intensity)

## Configuration

Environment variables (set in `.env`):

```bash
REDIS_URL=redis://172.31.42.185:6379
UPLOAD_DIR=uploads
PROCESSED_DIR=processed
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=jpg,jpeg,png,gif,bmp,tiff
```

## AWS ECS Deployment

1. **Build Docker image:**
   ```bash
   docker build -t image-processor .
   ```

2. **Push to ECR:**
   ```bash
   # Tag and push to your ECR repository
   docker tag image-processor:latest {account}.dkr.ecr.{region}.amazonaws.com/image-processor:latest
   docker push {account}.dkr.ecr.{region}.amazonaws.com/image-processor:latest
   ```

3. **Deploy to ECS:**
   - Use the provided task definition
   - Configure environment variables
   - Set up load balancer
   - Configure auto-scaling

## Redis Setup

This application uses Redis for:
- **Caching** - Image metadata and processing results
- **Job Management** - Background processing status
- **Session Storage** - Temporary data storage

### Redis Configuration
- Host: `172.31.42.185` (your AWS Redis instance)
- Port: `6379`
- No authentication required (VPC secured)

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   Client App    │───▶│  FastAPI API │───▶│    Redis    │
└─────────────────┘    └──────────────┘    └─────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ Image Storage│
                       │ (uploads/    │
                       │  processed/) │
                       └──────────────┘
```

## Performance

- **Async Processing** - Non-blocking image operations
- **Redis Caching** - Fast metadata and result retrieval
- **Background Jobs** - CPU-intensive tasks don't block API
- **Docker Optimized** - Minimal image size and fast startup

## Monitoring

Health check endpoint provides:
- Redis connection status
- Service availability
- System uptime
- Processing queue status

## Support

For issues or questions, check the logs:
```bash
docker-compose logs -f app
```
