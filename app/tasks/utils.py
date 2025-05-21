import asyncio
import logging
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.recommendations import Recommendation, UserRecommendation
from app.models.user import User
from app.services.recommendation_service import stream_genie_recommendations
from app.schemas.users import Archetype, Keyword

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
    archetypes: Optional[List[Archetype]] = None,
    keywords: Optional[List[Keyword]] = None,
    location: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> List[dict]:
    """
    Run the async recommendation service and collect all results.
    """
    recommendations = []
    try:
        async for recommendation in stream_genie_recommendations(
            time_of_day=time_of_day,
            archetypes=archetypes,
            keywords=keywords,
            location=location,
            ip_address=ip_address,
        ):
            recommendations.append(recommendation)
    except Exception as e:
        logger.error(f"Error in recommendation stream: {str(e)}")
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
        print(f"Storing recommendations for user {user_id}, recommendations: {recommendations_data}")
        recommendations_result = recommendations_data[0]
        recommendations = recommendations_result["recommendations"]
        
        for rec_data in recommendations:
            # Create recommendation
            recommendation = Recommendation(
                category=rec_data.get("category", "general"),
                prompt=rec_data.get("prompt", ""),
                search_query=rec_data.get("searchQuery"),
                place_details=rec_data.get("placeDetails", {}),
                archetypes=rec_data.get("usedArchetypes", []),
                keywords=rec_data.get("usedKeywords", []),
                image_concept=rec_data.get("recommendedImageConcept"),
                image_url=rec_data.get("recommendedImage"),
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

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get a user by their unique identifier.
    """
    user = db.query(User).get(user_id)
    return user
