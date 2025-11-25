#!/bin/bash

# Bragi Builder - Application Restart Script
# This script checks for running instances, shuts them down, and restarts the application

APP_NAME="bragi_builder"
APP_FILE="app.py"
PORT=8080
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔍 Checking for running instances of $APP_NAME..."

# Find all processes running app.py or using port 8080
PIDS=$(lsof -ti:$PORT 2>/dev/null)
PYTHON_PIDS=$(ps aux | grep -E "python.*app\.py|flask.*app|socketio" | grep -v grep | awk '{print $2}')

# Combine and deduplicate PIDs
ALL_PIDS=$(echo "$PIDS $PYTHON_PIDS" | tr ' ' '\n' | sort -u | tr '\n' ' ')

if [ -z "$ALL_PIDS" ]; then
    echo "✅ No running instances found."
    INSTANCE_COUNT=0
else
    INSTANCE_COUNT=$(echo "$ALL_PIDS" | wc -w | tr -d ' ')
    echo "⚠️  Found $INSTANCE_COUNT running instance(s):"
    for PID in $ALL_PIDS; do
        if [ ! -z "$PID" ]; then
            PROCESS_INFO=$(ps -p $PID -o pid,command --no-headers 2>/dev/null)
            if [ ! -z "$PROCESS_INFO" ]; then
                echo "   PID $PID: $PROCESS_INFO"
            fi
        fi
    done
    
    echo ""
    echo "🛑 Shutting down instances..."
    for PID in $ALL_PIDS; do
        if [ ! -z "$PID" ]; then
            if kill -0 $PID 2>/dev/null; then
                echo "   Stopping PID $PID..."
                kill $PID 2>/dev/null
                sleep 1
                # Force kill if still running
                if kill -0 $PID 2>/dev/null; then
                    echo "   Force killing PID $PID..."
                    kill -9 $PID 2>/dev/null
                fi
            fi
        fi
    done
    
    # Wait a moment for processes to fully terminate
    sleep 2
    
    # Verify all processes are stopped
    REMAINING=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$REMAINING" ]; then
        echo "⚠️  Some processes may still be running. Force killing..."
        kill -9 $REMAINING 2>/dev/null
        sleep 1
    fi
    
    echo "✅ All instances stopped."
fi

echo ""
echo "🚀 Starting application..."

# Change to script directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "   Using virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "   Using virtual environment..."
    source .venv/bin/activate
fi

# Start the application in the background
nohup python3 "$APP_FILE" > app.log 2>&1 &
NEW_PID=$!

# Wait a moment for the app to start
sleep 3

# Check if the process is still running
if kill -0 $NEW_PID 2>/dev/null; then
    echo "✅ Application started successfully!"
    echo "   PID: $NEW_PID"
    echo "   Port: $PORT"
    echo "   Log file: app.log"
    echo ""
    echo "📊 Summary:"
    echo "   Instances found: $INSTANCE_COUNT"
    echo "   Instances stopped: $INSTANCE_COUNT"
    echo "   New instance started: 1"
    echo ""
    echo "🌐 Access the application at: http://localhost:$PORT"
else
    echo "❌ Failed to start application. Check app.log for details."
    exit 1
fi



