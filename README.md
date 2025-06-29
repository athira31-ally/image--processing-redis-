# Image Processing System

A high-performance image processing API built with FastAPI and Celery, deployed on AWS Fargate with Redis for task queuing.

## 🚀 Live Demo
- **API Endpoint**: http://54.221.67.80:8000
- **Interactive Docs**: http://54.221.67.80:8000/docs
- **Health Check**: http://54.221.67.80:8000/

## Features
- 🚀 **FastAPI** - High-performance async web framework
- 📦 **Redis Integration** - Task queuing and caching
- 🖼️ **Image Processing** - Resize, blur, sharpen, filters, and more
- ⚡ **Celery Workers** - Background image processing
- 🐳 **Docker Ready** - Containerized for easy deployment
- ☁️ **AWS Fargate** - Serverless container deployment
- 🔄 **Auto-scaling** - Scales based on demand

## Architecture

```
Internet → ALB → AWS Fargate (ECS)
    ├── FastAPI Container (API Server)
    ├── Celery Worker Container (Background Tasks)
    └── Redis (EC2) - Task Queue & Cache
```

## Quick Start

### Local Development
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Start Redis locally:**
   ```bash
   docker run -d -p 6379:6379 redis:alpine
   ```
3. **Start the application:**
   ```bash
   ./start.sh
   ```
4. **Test the API:**
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
- `GET /` - Health check and worker status
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

## AWS Deployment Guide

### Prerequisites
- AWS CLI installed and configured
- Docker installed
- AWS account with appropriate permissions

### Step 1: Set up Redis on EC2

1. **Launch EC2 Instance:**
   ```bash
   # Launch a t3.micro instance (free tier eligible)
   aws ec2 run-instances \
     --image-id ami-0c02fb55956c7d316 \
     --instance-type t3.micro \
     --key-name your-key-pair \
     --security-group-ids sg-xxxxxxxxx \
     --subnet-id subnet-xxxxxxxxx \
     --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=redis-server}]'
   ```

2. **Configure Security Group for Redis:**
   ```bash
   # Allow Redis port 6379 from your ECS security group
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xxxxxxxxx \
     --protocol tcp \
     --port 6379 \
     --source-group sg-your-ecs-security-group
   ```

3. **Install Redis on EC2:**
   ```bash
   # SSH into your EC2 instance
   ssh -i your-key.pem ec2-user@your-ec2-ip
   
   # Install Redis
   sudo yum update -y
   sudo yum install -y redis
   
   # Configure Redis
   sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis.conf
   sudo sed -i 's/protected-mode yes/protected-mode no/' /etc/redis.conf
   
   # Start Redis
   sudo systemctl start redis
   sudo systemctl enable redis
   
   # Verify Redis is running
   redis-cli ping
   ```

### Step 2: Create ECR Repository

1. **Create ECR repository:**
   ```bash
   aws ecr create-repository --repository-name image-processor --region us-east-1
   ```

2. **Get login token:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
   ```

### Step 3: Build and Push Docker Image

1. **Build the image:**
   ```bash
   docker build -t image-processor .
   ```

2. **Tag and push:**
   ```bash
   docker tag image-processor:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/image-processor:latest
   docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/image-processor:latest
   ```

### Step 4: Create ECS Cluster

1. **Create cluster:**
   ```bash
   aws ecs create-cluster --cluster-name image-processing-cluster --region us-east-1
   ```

### Step 5: Create Task Definition

1. **Register task definition:**
   ```bash
   aws ecs register-task-definition --cli-input-json file://final-task-def.json --region us-east-1
   ```

   **Sample Task Definition (final-task-def.json):**
   ```json
   {
     "family": "image-processor-task",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/ecsTaskExecutionRole",
     "containerDefinitions": [
       {
         "name": "image-processor",
         "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/image-processor:latest",
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "REDIS_URL",
             "value": "redis://YOUR_REDIS_EC2_PRIVATE_IP:6379"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/image-processor",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "api"
           }
         }
       },
       {
         "name": "celery-worker",
         "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/image-processor:latest",
         "command": ["celery", "-A", "celery_worker", "worker", "--loglevel=info"],
         "environment": [
           {
             "name": "REDIS_URL",
             "value": "redis://YOUR_REDIS_EC2_PRIVATE_IP:6379"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/image-processor",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "celery"
           }
         }
       }
     ]
   }
   ```

### Step 6: Create CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name "/ecs/image-processor" --region us-east-1
```

### Step 7: Create ECS Service

1. **Create service:**
   ```bash
   aws ecs create-service \
     --cluster image-processing-cluster \
     --service-name image-processor-service \
     --task-definition image-processor-task:1 \
     --desired-count 1 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxxx,subnet-yyyyyyyyy],securityGroups=[sg-xxxxxxxxx],assignPublicIp=ENABLED}" \
     --region us-east-1
   ```

### Step 8: Configure Security Groups

1. **ECS Security Group (for Fargate tasks):**
   ```bash
   # Allow inbound HTTP traffic on port 8000
   aws ec2 authorize-security-group-ingress \
     --group-id sg-your-ecs-security-group \
     --protocol tcp \
     --port 8000 \
     --cidr 0.0.0.0/0
   
   # Allow outbound to Redis
   aws ec2 authorize-security-group-egress \
     --group-id sg-your-ecs-security-group \
     --protocol tcp \
     --port 6379 \
     --destination-group sg-your-redis-security-group
   ```

## Configuration

Environment variables (set in `.env` for local development):
```bash
REDIS_URL=redis://172.31.30.18:6379
UPLOAD_DIR=uploads
PROCESSED_DIR=processed
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=jpg,jpeg,png,gif,bmp,tiff
```

## Monitoring and Management

### Check Service Status
```bash
# Check ECS service
aws ecs describe-services --cluster image-processing-cluster --services image-processor-service --region us-east-1

# Check task health
aws ecs list-tasks --cluster image-processing-cluster --service-name image-processor-service --region us-east-1

# View logs
aws logs get-log-events --log-group-name "/ecs/image-processor" --log-stream-name "api/image-processor/TASK_ID" --region us-east-1
```

### Scale the Service
```bash
# Scale to 3 instances
aws ecs update-service \
  --cluster image-processing-cluster \
  --service image-processor-service \
  --desired-count 3 \
  --region us-east-1
```




## Current Deployment

- **ECS Cluster**: image-processing-cluster
- **Service**: image-processor-service
- **Task Definition**: image-processor-task:10
- **Public IP**: 54.221.67.80
- **Redis Server**: 172.31.30.18:6379
- **Region**: us-east-1
