# Gunicorn configuration file
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 2
threads = 4
timeout = 600
worker_class = "eventlet"
loglevel = "info"
chdir = "/home/site/wwwroot"
pythonpath = "/home/site/wwwroot"
