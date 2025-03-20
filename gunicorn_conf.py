import multiprocessing

# Gunicorn config
bind = "0.0.0.0:8000"  # Match this port in your ALB target group
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"