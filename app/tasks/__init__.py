from app.tasks.celery_app import celery_app
from app.tasks.recommendation_tasks import (
    generate_user_recommendations,
    generate_custom_recommendations,
    generate_entertainment_recommendations
)

__all__ = [
    "celery_app",
    "generate_user_recommendations",
    "generate_custom_recommendations",
    "generate_entertainment_recommendations"
] 