import asyncio
import logging
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.recommendations import Recommendation, UserRecommendation
from app.models.user import User
from app.services.recommendation_service import stream_genie_recommendations, stream_entertainment_recommendations
from enum import Enum

logger = logging.getLogger(__name__)

def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

async def run_async_recommendations(
    time_of_day: str,
    prompt: str,
    neighborhood: Optional[str] = None,
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
            time_of_day=time_of_day,
            prompt=prompt,
            neighborhood=neighborhood,
            latitude=latitude,
            longitude=longitude,
            ip_address=ip_address,
        ):
            recommendations.append(recommendation)
    except Exception as e:
        logger.error(f"Error in recommendation stream: {str(e)}")
        raise
    return recommendations

async def run_async_entertainment_recommendations(prompt: str) -> List[dict]:
    """
    Run the async entertainment recommendation service and collect all results.
    """
    recommendations = []
    try:
        async for recommendation in stream_entertainment_recommendations(prompt):
            recommendations.append(recommendation)
    except Exception as e:
        logger.error(f"Error in entertainment recommendation stream: {str(e)}")
        raise
    return recommendations

def store_recommendations(
    db: Session,
    user_id: int,
    recommendations_data: List[dict]
) -> List[Recommendation]:
    """
    Store recommendations in the database.
    """
    try:
        stored_recommendations = []
        recommendations_result = recommendations_data[0]
        recommendations = recommendations_result["structuredResults"]
        
        for rec_data in recommendations:
            places_data = rec_data.get("places", [])
            place_data = places_data[0] if places_data else {}
            if 'photos' in place_data:
                picture_url = place_data['photos'][0]['medium']
            else:
                picture_url = None
            
            if 'name' in place_data and rec_data.get("llmDescription") != "N/A":
                # Create recommendation
                recommendation = Recommendation(
                    category=place_data.get("category", "general"),
                    prompt=rec_data.get("llmDescription", ""),
                    search_query=rec_data.get("name"),
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
        
        db.commit()
        return stored_recommendations
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing recommendations: {str(e)}")
        raise 

class EntertainmentType(str, Enum):
    """Enum for entertainment content types."""
    TV_SHOWS = "Best TV shows to watch"
    MOVIES = "Best movies to watch"

def store_entertainment_recommendations(
    db: Session,
    user_id: int,
    entertainment_type: EntertainmentType,
    recommendations_data: List[dict]
) -> List[Recommendation]:
    """
    Store recommendations in the database.
    """
    try:
        stored_recommendations = []
        
        for rec_data in recommendations_data:
            recommendation_dict = rec_data.get("result")
            if recommendation_dict:
                if entertainment_type == EntertainmentType.TV_SHOWS:
                    category = "tv_shows"
                elif entertainment_type == EntertainmentType.MOVIES:
                    category = "movies"

                if entertainment_type == EntertainmentType.MOVIES:
                    picture_url = recommendation_dict.get("poster_path")
                    name = recommendation_dict.get("original_title")
                elif entertainment_type == EntertainmentType.TV_SHOWS:
                    picture_url = recommendation_dict.get("backdrop_path")
                    name = recommendation_dict.get("original_name")
                
                # Create recommendation
                recommendation = Recommendation(
                    category=category,
                    prompt=recommendation_dict.get("overview", ""),
                    search_query=name,
                    place_details={},
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
        
        db.commit()
        return stored_recommendations
    except Exception as e:
        db.rollback()
        logger.error(f"Error storing recommendations: {str(e)}")
        raise

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get a user by their unique identifier.
    """
    user = db.query(User).get(user_id)
    return user