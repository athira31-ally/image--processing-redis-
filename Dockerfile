FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p uploads processed

# Expose port
EXPOSE 8000

# Start script that runs both FastAPI and Celery worker
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
