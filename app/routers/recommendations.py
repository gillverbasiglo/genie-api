import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI, OpenAIError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional, List
from enum import Enum

from app.common import get_current_user
from app.config import settings
from app.init_db import get_db
from app.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Define the Recommendation model
class RecommendationRequest(BaseModel):
    location: str
    provider: str = "groq"
    model: str = "llama-3.1-8b-instant"

class Recommendation(BaseModel):
    """
    A recommendation is a personalized travel recommendation for a user.
    """
    id: str
    category: str
    prompt: str
    searchQuery: str
    usedArchetypes: List[str]
    usedKeywords: List[str]
    recommendedImage: str

# Global clients
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=settings.groq_api_key.get_secret_value()
)

openai_client = OpenAI(
    api_key=settings.openai_api_key.get_secret_value()
)

# Define the system prompt
SYSTEM_PROMPT = """
You are a helpful travel assistant specialized in generating personalized travel recommendations. Your responses must always be structured in valid JSON. Each recommendation should be clearly categorized into one of the following categories:

- restaurants
- coffee shops
- landmarks
- events
- unique local experiences

For each recommendation, include:
- prompt (concise, personalized description)
- searchQuery (exact place name optimized for PlacesAPI, no quotes)
- category (exactly one of the provided categories)
- usedArchetypes (list of relevant archetypes)
- usedKeywords (list of relevant keywords)
- recommendedImage (select the most appropriate image name from these options:
          * restaurant1 or restaurant2: For food, dining, or restaurant recommendations
          * relax1 or relax2: For relaxation places, spas, hotels, quiet spots, or scenic views
          * adventurer1 or adventurer2: For outdoor activities, adventure sports, or exploration sites)


Return **only** JSON with no additional text or markdown.
"""

recommendation_categories = [
    "restaurants",
    "coffee shops",
    "landmarks",
    "events",
    "unique local experiences"
]
    
@router.post("/generate", response_model=List[Recommendation])
async def generate_recommendations(
    request: RecommendationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate recommendations for a user based on their archetypes and keywords.
    
    Args:
        request: The recommendation request containing location, provider, and model
        current_user: The current user's information
        
    Returns:
        List of recommendations
    """
    logger.info(f"Generating recommendations for user: {current_user['uid']}")
    
    # Get user archetypes and keywords
    stmt = select(User).where(User.id == current_user["uid"])
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    archetypes = user.archetypes
    keywords = user.keywords

    archetypes_str = ', '.join(archetypes)
    keywords_str = ', '.join(keywords)

    if request.provider == "groq" and request.model.startswith('llama'):
        client = groq_client

        # create a list of tasks coroutines
        tasks = [generate_recommendation_for_category(category, request.location, keywords_str, archetypes_str, client) for category in recommendation_categories]
        if tasks:
            # run all tasks in parallel
            recommendations_tasks = await asyncio.gather(*tasks)
            # process results and filter out any errors
            recommendations = []
            for i, result in enumerate(recommendations_tasks):
                if isinstance(result, Exception):
                    logger.error(f"Error generating recommendation for category {recommendation_categories[i]}: {result}")
                else:
                    recommendation = Recommendation(
                        id=str(uuid.uuid4()),
                        category=recommendation_categories[i],
                        prompt=result["prompt"],
                        searchQuery=result["searchQuery"],
                        usedArchetypes=result["usedArchetypes"],
                    )
                    recommendations.append(recommendation)
            return recommendations
        else:
            raise HTTPException(status_code=400, detail="No recommendations found")
            
    elif request.provider == "openai" and request.model.startswith('gpt'):
        client = openai_client

        # create a list of tasks coroutines
        tasks = [generate_recommendation_for_category(category, request.location, keywords_str, archetypes_str, client) for category in recommendation_categories]
        if tasks:
            # run all tasks in parallel
            recommendations_tasks = await asyncio.gather(*tasks)
            # process results and filter out any errors
            recommendations = []
            for i, result in enumerate(recommendations_tasks):
                if isinstance(result, Exception):
                    logger.error(f"Error generating recommendation for category {recommendation_categories[i]}: {result}")
                else:
                    recommendation = Recommendation(
                        id=str(uuid.uuid4()),
                        category=recommendation_categories[i],
                        prompt=result["prompt"],
                        searchQuery=result["searchQuery"],
                        usedArchetypes=result["usedArchetypes"],
                    )
                    recommendations.append(recommendation)
            return recommendations
        else:
            raise HTTPException(status_code=400, detail="No recommendations found")
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")


async def generate_recommendation_for_category(
    category: str,
    location: str,
    keywords_str: str,
    archetypes_str: str,
    client: OpenAI
):
    user_prompt = f"""
    Generate exactly 1 personalized {category} recommendations based on:

    - Location: {location}
    - Interests: {keywords_str}
    - Archetypes: {archetypes_str}

    Return only JSON.
    """

    response = client.chat.completions.create(
        model=request.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response.choices[0].message.content

