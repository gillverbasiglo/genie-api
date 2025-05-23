import asyncio
from typing import List, Optional
from celery import Task
from celery.utils.log import get_task_logger
from app.tasks.celery_app import celery_app
from app.tasks.utils import get_db, run_async_recommendations, store_recommendations, get_user_by_id
from app.schemas.users import Archetype, Keyword

logger = get_task_logger(__name__)

class BaseTaskWithRetry(Task):
    """Base task class with retry logic."""
    max_retries = 1
    default_retry_delay = 60  # 1 minute

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failure using Celery's task logger."""
        logger.error(
            "Task failed",
            exc_info=exc,
            extra={
                "task_id": task_id,
                "args": args,
                "kwargs": kwargs
            }
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="generate_user_recommendations"
)
def generate_user_recommendations(
    self,
    user_id: int,
    ip_address: str,
    time_of_day: str
) -> dict:
    """
    Generate recommendations for a user based on their IP address.
    """
    logger.info(
        "Starting user recommendations generation",
        extra={
            "user_id": user_id,
            "ip_address": ip_address,
            "time_of_day": time_of_day
        }
    )
    
    try:
        db = get_db()
        recommendations = asyncio.run(
            run_async_recommendations(
                time_of_day=time_of_day,
                ip_address=ip_address
            )
        )
        
        stored_recommendations = store_recommendations(
            db=db,
            user_id=user_id,
            recommendations_data=recommendations
        )
        
        logger.info(
            "Successfully generated and stored recommendations",
            extra={
                "user_id": user_id,
                "recommendation_count": len(stored_recommendations)
            }
        )
        
        return {
            "status": "success",
            "user_id": user_id,
            "recommendation_count": len(stored_recommendations)
        }
        
    except Exception as e:
        logger.error(
            "Error generating user recommendations",
            exc_info=e,
            extra={"user_id": user_id}
        )
        raise self.retry(exc=e)

@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="generate_custom_recommendations"
)
def generate_custom_recommendations(
    self,
    user_id: int,
    time_of_day: str,
    location: str,
) -> dict:
    """
    Generate recommendations with custom parameters.
    """
    logger.info(
        "Starting custom recommendations generation",
        extra={
            "user_id": user_id,
            "time_of_day": time_of_day,
            "location": location
        }
    )
    
    try:
        db = get_db()
        user = get_user_by_id(db, user_id)
        keywords = user.keywords
        archetypes = user.archetypes
        
        recommendations = asyncio.run(
            run_async_recommendations(
                time_of_day=time_of_day,
                location=location,
                keywords=keywords,
                archetypes=archetypes
            )
        )
        
        stored_recommendations = store_recommendations(
            db=db,
            user_id=user_id,
            recommendations_data=recommendations
        )
        
        logger.info(
            "Successfully generated and stored custom recommendations",
            extra={
                "user_id": user_id,
                "recommendation_count": len(stored_recommendations)
            }
        )
        
        return {
            "status": "success",
            "user_id": user_id,
            "recommendation_count": len(stored_recommendations)
        }
        
    except Exception as e:
        logger.error(
            "Error generating custom recommendations",
            exc_info=e,
            extra={"user_id": user_id}
        )
        raise self.retry(exc=e) 