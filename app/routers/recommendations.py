import asyncio
import json
import logging
import uuid
from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_exponential

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
    archetypes: str
    keywords: str

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
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=settings.groq_api_key.get_secret_value()
)

openai_client = AsyncOpenAI(
    api_key=settings.openai_api_key.get_secret_value()
)

# Define the system prompt
SYSTEM_PROMPT = """You are a travel assistant specialized in generating EXACT place recommendations. Your recommendations must be specific places, not general areas or types of places. Each recommendation must be returned through the generate_recommendation function with:

- category: Must be one of the allowed categories
- prompt: A concise, inviting description of the specific place
- searchQuery: MUST BE an exact place name (e.g., "Starbucks Downtown Frederick", not "coffee shops in Frederick")
- usedArchetypes and usedKeywords: Only those relevant to this specific place
- recommendedImage: Choose based on the place type:
  * restaurant1 or restaurant2: For specific restaurants or dining venues
  * relax1 or relax2: For specific relaxation spots, spas, or scenic locations
  * adventurer1 or adventurer2: For specific activity venues or landmarks

IMPORTANT: The searchQuery MUST be an exact place name that exists and can be found on Google Places API.
"""

recommendation_categories = [
    "restaurants",
    "coffee shops",
    "landmarks",
    "events",
    "unique local experiences"
]

FUNCTION_SCHEMA = {
    "name": "generate_recommendation",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": recommendation_categories},
            "prompt": {"type": "string"},
            "searchQuery": {"type": "string"},
            "usedArchetypes": {"type": "array", "items": {"type": "string"}},
            "usedKeywords": {"type": "array", "items": {"type": "string"}},
            "recommendedImage": {
                "type": "string",
                "enum": ["restaurant1", "restaurant2", "relax1", "relax2", "adventurer1", "adventurer2"]
            }
        },
        "required": ["category", "prompt", "searchQuery", "usedArchetypes", "usedKeywords", "recommendedImage"]
    }
}

@router.post("/generate", response_model=List[Recommendation])
# @cache(expire=timedelta(hours=24), key_builder=lambda r: f"{r.location}:{r.archetypes}:{r.keywords}")
async def generate_recommendations(
    request: RecommendationRequest,
    db: Session = Depends(get_db)
):
    try:
        client = groq_client if request.provider == "groq" else openai_client
        
        # Generate recommendations for each category
        recommendation_tasks = [
            generate_batch_recommendations(
                client=client,
                location=request.location,
                keywords=request.keywords,
                archetypes=request.archetypes,
                category=category,
                model=request.model
            )
            for category in recommendation_categories
        ]
        
        if recommendation_tasks:
            recommendations = await asyncio.gather(*recommendation_tasks, return_exceptions=True)
            # Process results and filter out any errors
            processed_recommendations = []
            for i, result in enumerate(recommendations):
                if isinstance(result, Exception):
                    logger.error(f"Error generating recommendations for category {recommendation_categories[i]}: {result}")
                else:
                    processed_recommendations.append(result[0])
            
            print(processed_recommendations)
            return [Recommendation(id=str(uuid.uuid4()), **rec) for rec in processed_recommendations]
            
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_batch_recommendations(
    client: AsyncOpenAI,
    location: str,
    keywords: str,
    archetypes: str,
    category: str = "coffee shop",
    model: str = "gpt-3.5-turbo"
) -> List[dict]:
    """Generate recommendations for 1 category in a single API call"""
    
    user_prompt = f"""
    Generate exactly 1 {category} recommendation for a SPECIFIC PLACE (not a general area) that matches these criteria:

    Location: {location}
    Interests: {keywords}
    Archetypes: {archetypes}

    REQUIREMENTS:
    1. The searchQuery MUST be an exact place name (e.g., "Starbucks Reserve Frederick", not "coffee shops near Frederick")
    2. The place must actually exist and be findable on Google Maps
    3. The place must be relevant to the user's interests and archetypes
    4. The recommendation must be for a specific venue, not a type of place

    Example format for searchQuery:
    ✓ "Cafe Nola Frederick" (specific place)
    ✗ "cafes in Frederick" (too general)
    ✓ "Baker Park Frederick" (specific place)
    ✗ "parks near Frederick" (too general)
    """
    
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        functions=[FUNCTION_SCHEMA],
        function_call={"name": "generate_recommendation"},
        temperature=0.6,  # Slightly lower temperature for more focused results
        n=1
    )
    
    return [
        json.loads(choice.message.function_call.arguments)
        for choice in response.choices
        if choice.message.function_call
    ]
