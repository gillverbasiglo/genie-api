import asyncio
import logging
from contextlib import contextmanager
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.recommendations import Recommendation, UserRecommendation
from app.models.user import User
from app.services.recommendation_service import stream_genie_recommendations, stream_entertainment_recommendations
from enum import Enum

logger = logging.getLogger(__name__)

# Global engine to avoid recreating it every time
_engine = None
_SessionLocal = None

def _get_engine():
    """Get or create a database engine with credential refresh support."""
    global _engine, _SessionLocal
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{settings.db_username}:{settings.db_password.get_secret_value()}@{settings.host}:{settings.port}/{settings.database}"
            
            # Create a new engine if it doesn't exist or credentials might have changed
            if _engine is None:
                _engine = create_engine(
                    SQLALCHEMY_DATABASE_URL,
                    pool_pre_ping=True,  # Validate connections before use
                    pool_recycle=3600,   # Recycle connections every hour
                    pool_size=5,
                    max_overflow=10
                )
                _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
                logger.info("Created new database engine")
            
            # Test the connection
            with _SessionLocal() as test_session:
                test_session.execute(text("SELECT 1"))
            
            return _engine, _SessionLocal
            
        except Exception as e:
            # Reset global engine on error
            _engine = None
            _SessionLocal = None
            
            # Check if it's an authentication error
            error_msg = str(e).lower()
            if ('authentication' in error_msg or 'password' in error_msg or 'login' in error_msg) and retry_count < max_retries:
                logger.warning(f"Database authentication failed (retry {retry_count + 1}): {e}")
                
                # Clear secrets cache and refresh credentials if in production
                if settings.environment == "production":
                    from app.secrets_manager import SecretsManager
                    secrets_manager = SecretsManager(region_name=settings.aws_region)
                    secrets_manager.clear_cache()
                    logger.info("Cleared secrets cache, will retry with fresh credentials")
                
                retry_count += 1
                continue
            else:
                logger.error(f"Database connection failed: {e}")
                raise

@contextmanager
def get_db():
    """Get a database session context manager with proper lifecycle management."""
    engine, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
        logger.debug("Database session committed successfully")
    except Exception:
        session.rollback()
        logger.error("Database session rolled back due to error")
        raise
    finally:
        session.close()
        logger.debug("Database session closed")

async def run_async_recommendations(
    user_id: str,
    time_of_day: str,
    neighborhood: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    ip_address: Optional[str] = None,
) -> List[dict]:
    """
    Run the async recommendation service and collect all results.
    """
    recommendations = []
    try:
        async for recommendation in stream_genie_recommendations(
            user_id=user_id,
            time_of_day=time_of_day,
            neighborhood=neighborhood,
            city=city,
            country=country,
            latitude=latitude,
            longitude=longitude,
            ip_address=ip_address,
        ):
            recommendations.append(recommendation)
    except Exception as e:
        logger.error(f"Error in recommendation stream: {str(e)}")
        raise
    return recommendations

async def run_async_entertainment_recommendations(user_id: str) -> List[dict]:
    """
    Run the async entertainment recommendation service and collect all results.
    """
    recommendations = []
    try:
        async for recommendation in stream_entertainment_recommendations(user_id):
            recommendations.append(recommendation)
    except Exception as e:
        logger.error(f"Error in entertainment recommendation stream: {str(e)}")
        raise
    return recommendations

def store_recommendations(
    user_id: str,
    recommendations_data: List[dict]
) -> List[Recommendation]:
    """
    Store recommendations in the database using a context manager.
    """
    with get_db() as db:
        stored_recommendations = []
        recommendations = recommendations_data
        
        for rec_data in recommendations:
            places_data = rec_data.get("results", [])
            place_data = places_data[0] if places_data else {}
            if 'photos' in place_data:
                picture_url = place_data['photos'][0]['large']
            else:
                picture_url = None

            if 'query' in rec_data and rec_data.get("why_would_you_like_this") != "N/A":
                # Create recommendation
                recommendation = Recommendation(
                    category=rec_data.get("category", "general"),
                    prompt=rec_data.get("why_would_you_like_this", ""),
                    search_query=place_data.get("name"),
                    place_details=place_data,
                    archetypes=rec_data.get("usedArchetypes", []),
                    keywords=rec_data.get("usedKeywords", []),
                    image_concept=rec_data.get("recommendedImageConcept"),
                    image_url=picture_url,
                    source=rec_data.get("source", "genie-ai"),
                    external_id=rec_data.get("external_id")
                )
                db.add(recommendation)
                db.flush()  # Get the ID without committing
                
                # Create user recommendation link
                user_recommendation = UserRecommendation(
                    user_id=user_id,
                    recommendation_id=recommendation.id,
                    is_seen=False
                )
                db.add(user_recommendation)
                stored_recommendations.append(recommendation)
        
        # Commit happens automatically in the context manager
        return stored_recommendations

def store_entertainment_recommendations(
    user_id: str,
    recommendations_data: List[dict]
) -> List[Recommendation]:
    """
    Store entertainment recommendations in the database using a context manager.
    """
    with get_db() as db:
        stored_recommendations = []

        for recommendation_dict in recommendations_data:
            if recommendation_dict.get('result', None):
                recommendation_dict = recommendation_dict.get('result')
                media_type = recommendation_dict.get("media_type")
                if media_type == "tv":
                    category = "tv_shows"
                    picture_url = recommendation_dict.get("backdrop_path") or recommendation_dict.get("poster_path")
                    name = (
                        recommendation_dict.get("original_name") or 
                        recommendation_dict.get("title") or
                        recommendation_dict.get("name")
                    )
                elif media_type == "movie":
                    category = "movies"
                    picture_url = recommendation_dict.get("poster_path")
                    name = (
                        recommendation_dict.get("original_title") or
                        recommendation_dict.get("title") or
                        recommendation_dict.get("name")
                    )
                
                # Create recommendation
                recommendation = Recommendation(
                    category=category,
                    prompt=recommendation_dict.get("why_would_you_like_this", ""),
                    search_query=name,
                    place_details=None,
                    archetypes=[recommendation_dict.get("usedArchetypes", [])],
                    keywords=recommendation_dict.get("usedKeywords", []),
                    image_concept=recommendation_dict.get("recommendedImageConcept"),
                    image_url=picture_url,
                    source=recommendation_dict.get("source", "genie-ai"),
                    external_id=recommendation_dict.get("external_id"),
                    resource_details=recommendation_dict
                )
                db.add(recommendation)
                db.flush()  # Get the ID without committing
                
                # Create user recommendation link
                user_recommendation = UserRecommendation(
                    user_id=user_id,
                    recommendation_id=recommendation.id,
                    is_seen=False
                )
                db.add(user_recommendation)
                stored_recommendations.append(recommendation)
        
        # Commit happens automatically in the context manager
        return stored_recommendations

def get_user_by_id(user_id: str) -> Optional[dict]:
    """
    Get user data needed for recommendations to avoid DetachedInstanceError.
    Returns a dict with archetypes and keywords instead of a User object.
    """
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Extract the data while the session is active
        return {
            'id': user.id,
            'archetypes': user.archetypes,
            'keywords': user.keywords
        }
