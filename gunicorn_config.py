# Gunicorn configuration file
import os

# Get port from environment (Azure sets PORT automatically)
port = os.getenv('PORT', os.getenv('WEBSITES_PORT', '8000'))
bind = f"0.0.0.0:{port}"
workers = 2
threads = 4
timeout = 600
worker_class = "eventlet"
loglevel = "info"
chdir = "/home/site/wwwroot"
pythonpath = "/home/site/wwwroot"

