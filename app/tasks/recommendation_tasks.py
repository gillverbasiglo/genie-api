import asyncio
import random
from typing import List
from celery import Task
from celery.utils.log import get_task_logger
from app.tasks.celery_app import celery_app
from app.tasks.utils import get_db, run_async_recommendations, store_recommendations, get_user_by_id, run_async_entertainment_recommendations, store_entertainment_recommendations

logger = get_task_logger(__name__)

class BaseTaskWithRetry(Task):
    """Base task class with retry logic."""
    max_retries = 1
    default_retry_delay = 60  # 1 minute

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failure using Celery's task logger."""
        logger.error(
            "Task failed: %s (task_id: %s, task_args: %s, task_kwargs: %s)",
            str(exc),
            task_id,
            args,
            kwargs,
            exc_info=exc
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

def get_random_subset(items: List[str], count: int = 5) -> List[str]:
    """Get a random subset of items, or all items if count is greater than available items."""
    if not items:
        return []
    return random.sample(items, min(count, len(items)))

@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="generate_user_recommendations"
)
def generate_user_recommendations(
    self,
    user_id: str,
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
        recommendations = asyncio.run(
            run_async_recommendations(
                time_of_day=time_of_day,
                ip_address=ip_address
            )
        )
        
        stored_recommendations = store_recommendations(
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
    user_id: str,
    time_of_day: str,
    neighborhood: str,
    city: str,
    country: str,
    latitude: float,
    longitude: float,
) -> dict:
    """
    Generate recommendations with custom parameters.
    Limits archetypes and keywords to 5 each for more focused recommendations.
    """
    logger.info(
        "Starting custom recommendations generation",
        extra={
            "user_id": user_id,
            "time_of_day": time_of_day,
            "neighborhood": neighborhood,
            "city": city,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
        }
    )
    
    try:
        user_data = get_user_by_id(user_id)
        if not user_data:
            raise ValueError(f"User with id {user_id} not found")
        
        # Get random subsets of archetypes and keywords
        selected_archetypes = get_random_subset(user_data.get('archetypes') or [], 5)
        selected_keywords = get_random_subset(user_data.get('keywords') or [], 5)

        selected_archetypes = [archetype['name'] for archetype in selected_archetypes]
        selected_keywords = [keyword['name'] for keyword in selected_keywords]
        
        logger.info(
            "Selected archetypes and keywords",
            extra={
                "user_id": user_id,
                "selected_archetypes": selected_archetypes,
                "selected_keywords": selected_keywords
            }
        )
        
        prompt = (
            f"Show me appropriate places for someone who is visiting my area and "
            f"possesses these archetypes: {', '.join(selected_archetypes)} and "
            f"interests: {', '.join(selected_keywords)}"
        )

        print(prompt)

        logger.info(
            "Prompt",
            extra={
                "prompt": prompt
            }
        )
        
        recommendations = asyncio.run(
            run_async_recommendations(
                user_id=user_id,
                time_of_day=time_of_day,
                prompt=prompt,
                neighborhood=neighborhood,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude
            )
        )
        
        stored_recommendations = store_recommendations(
            user_id=user_id,
            recommendations_data=recommendations
        )
        
        logger.info(
            "Successfully generated and stored custom recommendations",
            extra={
                "user_id": user_id,
                "recommendation_count": len(stored_recommendations),
                "used_archetypes": selected_archetypes,
                "used_keywords": selected_keywords
            }
        )
        
        return {
            "status": "success",
            "user_id": user_id,
            "recommendation_count": len(stored_recommendations),
            "used_archetypes": selected_archetypes,
            "used_keywords": selected_keywords
        }
        
    except Exception as e:
        logger.error(
            "Error generating custom recommendations",
            exc_info=e,
            extra={"user_id": user_id}
        )
        raise self.retry(exc=e) 
    
@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="generate_entertainment_recommendations"
)
def generate_entertainment_recommendations(
    self,
    user_id: str
) -> dict:
    """
    Generate movie recommendations for a user.
    """
    logger.info(
        "Starting movie recommendations generation",
        extra={
            "user_id": user_id
        }
    )

    try:
        recommendations = asyncio.run(
            run_async_entertainment_recommendations(user_id)
        )
        
        stored_recommendations = store_entertainment_recommendations(
            user_id=user_id,
            recommendations_data=recommendations,
        )

        logger.info(
            f"Successfully generated and stored {len(stored_recommendations)} recommendations for movies and tv shows",
        )
    except Exception as e:
        logger.error(
            "Error generating movie recommendations",
            exc_info=e,
            extra={"user_id": user_id}
        )
        raise self.retry(exc=e)