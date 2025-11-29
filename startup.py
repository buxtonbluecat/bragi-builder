#!/usr/bin/env python3
"""
Azure App Service startup script
This is an alternative to startup.sh - runs directly with Python
"""
import os
import sys

# Change to app directory
os.chdir('/home/site/wwwroot')

# Set port from environment
port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8000)))

# Import app after setting up environment
from app import app, socketio

if __name__ == '__main__':
    print(f"Starting Bragi Builder on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)



