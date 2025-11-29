# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /home/LogFiles /home/data

# Expose port (Azure will set PORT env var)
EXPOSE 8000

# Use gunicorn to run the app
# Azure App Service sets PORT automatically - use it if available
# Default to 8000 if PORT is not set (for local testing)
CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info app:app"


