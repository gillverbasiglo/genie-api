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
    All right, travel partner—let’s line up a handful of spots around {location} that will feel perfectly “us.”
    I’ll serve up to **{max_recommendations}** ideas, each chosen with your shared archetypes ({archetypes}) in mind, so you and {friend_name} can settle in, swap stories, and enjoy the place itself rather than fuss over the planning.

    For every suggestion I’ll make sure to:
    1. Pick a single, exact place or activity in {location} (no vague “best cafés nearby” stuff).
    2. Gently point out why it matches what the two of you typically gravitate toward—letting the place’s vibe and details do the convincing.
    3. Add the practical bits you’ll actually need: neighborhood, ideal time to go, a tip on what makes it stand out, and why it’s an easy meet‑up spot.

    **Extra details I’ll tuck into each entry**
    - **Title** – short and clear.
    - **Opening line** – a quick note on how the spot fits both of you (I’ll skip using your name, mention {friend_name} once, and stick to second‑person everywhere else).
    - **Personalized note** – a friendly aside connecting the pick to your shared archetypes, without claiming to read your mind.
    - **TOP 3 KEYWORDS** – chosen from: {", ".join(keywords[:20])}.
    - **TOP 3 ARCHETYPES** – pulled from {archetypes}.
    - **image** – just the single archetype or keyword that best sums up the recommendation.

    I’ll return everything in **pure JSON**—nothing else—using this structure (watch those commas and quotes!):

    {{
    "recommendations": [
        {{
        "title": "Name of Recommendation",
        "description": "Why this fits both of you, including subtle nods to shared interests and why it’s an inviting place to meet",
        "practical_tips": "Neighborhood, hours, best time, standout feature, and why it’s an easy rendezvous spot",
        "searchQuery": "Exact Place Name",
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "archetypes": ["archetype1", "archetype2", "archetype3"],
        "image": "most_relevant_term"
        }}
    ]
    }}

    I’ll keep the list varied—no wall‑to‑wall restaurants or all museums—and true to {location}’s character.
    And remember: **only the JSON comes back to you.**
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
