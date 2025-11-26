#!/bin/bash
# Startup script for Azure App Service
# This script is executed when the app starts

set -e  # Exit on error
set -x  # Debug mode

echo "Starting Bragi Builder application..."
echo "Current directory: $(pwd)"
echo "Python version: $(python3 --version)"
echo "Port: ${PORT:-8000}"

# Create necessary directories if they don't exist
mkdir -p /home/LogFiles
mkdir -p /home/data

# Change to app directory
cd /home/site/wwwroot || exit 1

# Set Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Get port from environment (Azure App Service sets PORT automatically)
PORT=${PORT:-8000}
export WEBSITES_PORT=$PORT

# Check if gunicorn is available
if command -v gunicorn &> /dev/null; then
    echo "Starting with gunicorn on port $PORT..."
    # Note: SocketIO requires eventlet or gevent worker class
    exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info app:app
else
    echo "Gunicorn not found, starting with Flask development server on port $PORT..."
    exec python3 app.py
fi
