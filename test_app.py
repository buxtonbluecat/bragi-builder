#!/usr/bin/env python3
"""
Minimal test Flask app to verify deployment works
"""
from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return f"Test app is working! Port: {os.getenv('PORT', 'not set')}"

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('WEBSITES_PORT', 8000)))
    app.run(host='0.0.0.0', port=port, debug=False)
