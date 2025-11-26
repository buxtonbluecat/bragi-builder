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

# Try multiple ways to find gunicorn
GUNICORN_CMD=""
if command -v gunicorn &> /dev/null; then
    GUNICORN_CMD="gunicorn"
elif python3 -m gunicorn --version &> /dev/null; then
    GUNICORN_CMD="python3 -m gunicorn"
elif [ -f "/opt/python/3.11.14/bin/gunicorn" ]; then
    GUNICORN_CMD="/opt/python/3.11.14/bin/gunicorn"
else
    echo "Gunicorn not found, installing..."
    pip3 install --user gunicorn eventlet || echo "Failed to install gunicorn"
    if python3 -m gunicorn --version &> /dev/null; then
        GUNICORN_CMD="python3 -m gunicorn"
    fi
fi

# Start the application
if [ -n "$GUNICORN_CMD" ]; then
    echo "Starting with $GUNICORN_CMD on port $PORT..."
    exec $GUNICORN_CMD --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 600 --worker-class eventlet --log-level info app:app
else
    echo "Gunicorn not available, starting with Flask development server on port $PORT..."
    exec python3 app.py
fi
