#!/bin/bash
# Don't exit on error immediately - let gunicorn handle errors
set +e

# Get port from environment variable, default to 8000
PORT=${PORT:-8000}

echo "Starting Bragi Builder on port $PORT..."
echo "Environment variables:"
echo "  PORT=${PORT}"
echo "  PWD=$(pwd)"
echo "  PYTHONPATH=${PYTHONPATH:-not set}"

# Verify app.py exists
if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found in $(pwd)"
    ls -la
    exit 1
fi

# Start gunicorn with the app
echo "Starting gunicorn..."
exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 4 \
    --timeout 600 \
    --worker-class eventlet \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:app
