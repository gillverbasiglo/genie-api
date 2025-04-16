import asyncio
import json
import logging
import uuid
import random

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
from app.services import get_user_by_id, find_common_archetypes, load_cover_images, select_cover_image, get_s3_image_url

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
    max_recommendations: int = 5
    user_prompt: Optional[str] = None

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

keywords = [
    "cooking", "baking", "wine tasting", "beer brewing", "mixology", "dancing",
    "stamp collecting", "vintage items", "skiing", "hiking", "cycling",
    "rock climbing", "kayaking", "yoga", "running", "swimming", "weightlifting",
    "playing tennis", "golf", "martial arts", "skateboarding", "surfing",
    "climbing", "boxing", "sailing", "bungee jumping", "adventure sports",
    "attractions and travel", "urban", "spa", "museums", "outdoors", "beach",
    "roadside", "wildlife", "camping", "playground", "national parks",
    "historical sites", "cultural landmarks", "scenic routes", "safari parks",
    "zoos", "resorts", "buildings", "romantic date", "date night", "nightlife",
    "board games", "karaoke", "picnic", "barbecue", "movies",
    "electronic music", "games", "art", "tech", "concerts",
    "opera", "music festivals", "theater", "exhibitions", "robotics",
    "education", "workshops", "designer", "architecture", "photography",
    "spa", "meditation", "yoga retreats"
]

# Define the system prompt
SYSTEM_PROMPT = """You are a travel assistant specialized in generating EXACT place recommendations. Your recommendations must be specific places, not general areas or types of places. Each recommendation must be returned through the generate_recommendation function with:

- category: Must be one of the allowed categories
- prompt: A concise, inviting description of the specific place
- searchQuery: MUST BE an exact place name (e.g., "Starbucks Downtown Frederick", not "coffee shops in Frederick")
- usedArchetypes and usedKeywords: Only those relevant to this specific place
- recommendedImage: You MUST populate this field with the most representative archetype or keyword for this recommendation (just the term itself, like "adventurer" or "hiking")

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

        if request.user_prompt:
            recommendations = await generate_recommendations_for_user_request(
                client=client,
                location=request.location,
                archetypes=request.archetypes,
                keywords=request.keywords,
                user_request=request.user_prompt,
                max_recommendations=request.max_recommendations,
                model=request.model
            )

            # Load cover images
            cover_images = load_cover_images()

            # Iterate through recommendations and add cover images using the value on the recommendedImage field
            for recommendation in recommendations:
                image_url = select_cover_image(cover_images, recommendation["recommendedImage"])
                recommendation["recommendedImage"] = get_s3_image_url(image_url)

            return [Recommendation(id=str(uuid.uuid4()), **rec) for rec in recommendations]
        else:
            # Randomly shuffle the recommendation categories based on max_recommendations
            categories = random.sample(recommendation_categories, request.max_recommendations)
            
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
                for category in categories
            ]
            
            if recommendation_tasks:
                recommendations = await asyncio.gather(*recommendation_tasks, return_exceptions=True)
                # Process results and filter out any errors
                processed_recommendations = []
                for i, result in enumerate(recommendations):
                    if isinstance(result, Exception):
                        logger.error(f"Error generating recommendations for category {categories[i]}: {result}")
                    else:
                        processed_recommendations.append(result[0])
                
                # Load cover images
                cover_images = load_cover_images()

                # Iterate through recommendations and add cover images using the value on the recommendedImage field
                for recommendation in processed_recommendations:
                    image_url = select_cover_image(cover_images, recommendation["recommendedImage"])
                    recommendation["recommendedImage"] = get_s3_image_url(image_url)

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

async def generate_recommendations_for_user_request(
    client: AsyncOpenAI,
    location: str,
    archetypes: str,
    keywords: str,
    user_request: str,
    max_recommendations: int = 3,
    model: str = "gpt-4o-mini"
) -> List[dict]:
    """Generate recommendations for a user's request"""

    # Build the prompt
    llm_prompt = f"""
    Generate exactly {max_recommendations} highly relevant and diverse places recommendations based on user's interests and archetypes that are around the user's current location.

    - Location: {location}
    - Interests: {keywords}
    - Archetypes: {archetypes}
    - User request: {user_request}

    IMPORTANT:
    - The recommendations MUST be unique and not repeat the same place
    - The recommendations MUST be relevant to the user's interests and archetypes
    - The recommendations MUST be specific places, not general areas or types of places
    """

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": llm_prompt}
        ],
        functions=[FUNCTION_SCHEMA],
        function_call={"name": "generate_recommendation"},
        temperature=0.6,  # Slightly lower temperature for more focused results
        n=max_recommendations
    )
    
    return [
        json.loads(choice.message.function_call.arguments)
        for choice in response.choices
        if choice.message.function_call
    ]

async def generate_friend_portal_recommendations(
    client: AsyncOpenAI,
    location: str,
    archetypes: str,
    user_name: str,
    friend_name: str,
    model: str = "gpt-4o-mini",
    max_recommendations: int = 3
) -> List[dict]:
    """Generate recommendations for a friend's portal"""

    # Build the prompt
    llm_prompt = f"""
    You are a travel and experience advisor for two friends named {user_name} and {friend_name} who share similar interests and are visiting {location}.

    Their common travel archetypes are: {archetypes}

    Based on these shared interests and their current location, provide {max_recommendations} specific recommendations that would appeal to both of them. Each recommendation should:
    1. Be a specific restaurant, attraction, or activity in {location}
    2. Explain why it matches their shared interests/archetypes
    3. Include practical details (location area, best time to visit, what makes it special)

    For each recommendation, ALSO include:
    - A clear title for the recommendation
    - Start with "For {user_name} and his friend {friend_name}..."
    - Include a personalized explanation of why this particular recommendation suits both {user_name} and {friend_name} based on their shared archetypes
    - Identify TOP 3 KEYWORDS from this list that match this recommendation: {", ".join(keywords[:20])}
    - Identify TOP 3 ARCHETYPES from this list that match this recommendation: {archetypes}
    - IMPORTANT: Include "image" field with the most representative archetype or keyword for this recommendation (just the term itself, like "adventurer" or "hiking")

    Format your response in JSON with the following structure:
    {{
      "recommendations": [
        {{
          "title": "Name of Recommendation",
          "description": "Detailed description of the recommendation including personalized explanation",
          "practical_tips": "Practical information like location, hours, etc.",
          "searchQuery": "MUST be an exact place name (e.g., "Starbucks Reserve Frederick", not "coffee shops near Frederick")",
          "keywords": ["keyword1", "keyword2", "keyword3"],
          "archetypes": ["archetype1", "archetype2", "archetype3"],
          "image": "most_relevant_term"
        }}
      ]
    }}

    Make sure the recommendations are diverse (not all restaurants or all museums).
    Recommendations should be authentic to {location}'s culture and geography.
    Return ONLY the JSON with no other text. Be extremely careful with JSON syntax - all quotes, commas, and brackets must be correctly placed.
    """

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful travel assistant specialized in tailoring recommendations based on travel archetypes and interests. Always respond with valid, properly formatted JSON. Be extremely careful with JSON syntax."
            },
            {
                "role": "user", 
                "content": llm_prompt
            }
        ],
        temperature=0.6,
        max_tokens=1500
    )
    
    return json.loads(response.choices[0].message.content)

class FriendPortalRecommendationRequest(BaseModel):
    location: str
    model: str = "Llama3-8b-8192"
    provider: str = "groq"
    max_recommendations: int = 3

@router.post("/friends/{friend_id}/portal", response_model=None)
async def get_friend_portal_recommendations(
    friend_id: str,
    request: FriendPortalRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user["uid"] == friend_id:
        raise HTTPException(status_code=403, detail="You cannot access your own portal through this endpoint")
    
    user = get_user_by_id(db, current_user["uid"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    friend = get_user_by_id(db, friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    
    if not user.archetypes or not friend.archetypes:
        raise HTTPException(status_code=400, detail="User or friend archetypes not found")
    
    try:
        common_archetypes = find_common_archetypes(user.archetypes, friend.archetypes)
        recommendations = await generate_friend_portal_recommendations(
            client=groq_client if request.provider == "groq" else openai_client,
            location=request.location,
            archetypes=", ".join(common_archetypes),
            user_name=user.display_name,
            friend_name=friend.display_name,
            model=request.model
        )

        # Load cover images
        cover_images = load_cover_images()

        # Iterate through recommendations and add cover images using the value on the image field
        for recommendation in recommendations["recommendations"]:
            image_category = recommendation["image"]
            image_url = select_cover_image(cover_images, image_category)
            recommendation["image"] = get_s3_image_url(image_url)

        return recommendations
    except Exception as e:
        logger.error(f"Error finding common archetypes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
