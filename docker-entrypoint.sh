#!/bin/bash
# Ensure errors are visible
set -x

# Get port from environment variable, default to 8000
PORT=${PORT:-8000}

# Write all output to stderr so Azure captures it
exec 1>&2

echo "Starting Bragi Builder on port $PORT..." >&2
echo "Environment variables:" >&2
echo "  PORT=${PORT}" >&2
echo "  PWD=$(pwd)" >&2
echo "  PYTHONPATH=${PYTHONPATH:-not set}" >&2

# Verify app.py exists
if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found in $(pwd)" >&2
    ls -la >&2
    exit 1
fi

# Start gunicorn with the app
echo "Starting gunicorn..." >&2
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
