#!/bin/bash
# Startup script for Azure App Service
# This script is executed when the app starts

echo "Starting Bragi Builder application..."

# Create necessary directories if they don't exist
mkdir -p /home/LogFiles
mkdir -p /home/data

# Set Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Get port from environment (Azure App Service sets PORT)
PORT=${PORT:-8000}

# Run the Flask application
# Use gunicorn for production (more stable than Flask dev server)
# If gunicorn is not available, fall back to the Flask dev server
if command -v gunicorn &> /dev/null; then
    echo "Starting with gunicorn on port $PORT..."
    # Note: SocketIO requires eventlet or gevent worker class
    gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info app:app
else
    echo "Starting with Flask development server on port $PORT..."
    export WEBSITES_PORT=$PORT
    python3 app.py
fi
