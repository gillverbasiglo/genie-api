import logging
import asyncio

from typing import List, Optional
from celery import Task
from app.tasks.celery_app import celery_app
from app.tasks.utils import get_db, run_async_recommendations, store_recommendations
from app.schemas.users import Archetype, Keyword

logger = logging.getLogger(__name__)

class BaseTaskWithRetry(Task):
    """Base task class with retry logic and logging."""
    max_retries = 1
    default_retry_delay = 60  # 1 minute

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failure."""
        logger.error(
            f"Task {self.name} failed: {exc}",
            extra={
                "task_id": task_id,
                "args": args,
                "kwargs": kwargs,
                "exception": str(exc)
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
    
    Args:
        user_id: The ID of the user
        ip_address: User's IP address for location detection
        time_of_day: Time of day (morning, afternoon, evening, night)
    """
    logger.info(
        f"Starting user recommendations generation",
        extra={
            "user_id": user_id,
            "ip_address": ip_address,
            "time_of_day": time_of_day
        }
    )
    
    try:
        # Get database session
        db = get_db()
        
        # Run async recommendations
        recommendations = asyncio.run(
            run_async_recommendations(
                time_of_day=time_of_day,
                ip_address=ip_address
            )
        )
        
        # Store recommendations
        stored_recommendations = store_recommendations(
            db=db,
            user_id=user_id,
            recommendations_data=recommendations
        )
        
        logger.info(
            f"Successfully generated and stored recommendations",
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
            f"Error generating user recommendations: {str(e)}",
            extra={
                "user_id": user_id,
                "error": str(e)
            }
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
    keywords: Optional[List[str]] = None,
    archetypes: Optional[List[str]] = None
) -> dict:
    """
    Generate recommendations with custom parameters.
    
    Args:
        user_id: The ID of the user
        time_of_day: Time of day (morning, afternoon, evening, night)
        location: Location string
        keywords: List of keyword strings
        archetypes: List of archetype strings
    """
    logger.info(
        f"Starting custom recommendations generation",
        extra={
            "user_id": user_id,
            "time_of_day": time_of_day,
            "location": location,
            "keywords": keywords,
            "archetypes": archetypes
        }
    )
    
    try:
        # Convert string lists to enums
        keyword_enums = [Keyword(k) for k in (keywords or [])]
        archetype_enums = [Archetype(a) for a in (archetypes or [])]
        
        # Get database session
        db = get_db()
        
        # Run async recommendations
        recommendations = asyncio.run(
            run_async_recommendations(
                time_of_day=time_of_day,
                location=location,
                keywords=keyword_enums,
                archetypes=archetype_enums
            )
        )
        
        # Store recommendations
        stored_recommendations = store_recommendations(
            db=db,
            user_id=user_id,
            recommendations=recommendations
        )
        
        logger.info(
            f"Successfully generated and stored custom recommendations",
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
            f"Error generating custom recommendations: {str(e)}",
            extra={
                "user_id": user_id,
                "error": str(e)
            }
        )
        raise self.retry(exc=e) 