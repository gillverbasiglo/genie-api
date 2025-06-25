import multiprocessing

# Gunicorn config
bind = "0.0.0.0:8000"  # Match this port in your ALB target group
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"