#!/bin/bash
set -e

# Get port from environment variable, default to 8000
PORT=${PORT:-8000}

echo "Starting Bragi Builder on port $PORT..."

# Start gunicorn with the app
exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 4 \
    --timeout 600 \
    --worker-class eventlet \
    --log-level info \
    app:app
