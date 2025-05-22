from celery import Celery

# RabbitMQ connection URL for broker
RABBITMQ_URL = "amqp://genie:genie123@localhost:5672//"

# Redis connection URL for result backend
REDIS_URL = "redis://localhost:6379/0"

celery_app = Celery(
    "genie_backend",
    broker=RABBITMQ_URL,
    backend=REDIS_URL,  # Using Redis as result backend
    include=["app.tasks.recommendation_tasks"]
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    worker_prefetch_multiplier=1,  # One task per worker
)

# Retry policy
celery_app.conf.task_routes = {
    "app.tasks.recommendation_tasks.*": {"queue": "recommendations"}
}

celery_app.conf.task_default_retry_delay = 60  # 1 minute
celery_app.conf.task_max_retries = 1  # Retry once 