import asyncio
import json
import logging
import uuid
import random

from typing import List, Union, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Response
from fastapi_cache.decorator import cache
from google import genai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func, null
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timezone
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from shapely.geometry import Point
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from app.common import get_current_user
from app.config import settings
from app.init_db import get_db
from app.models import User, UserRecommendation, Recommendation
from app.services import get_user_by_id, find_common_archetypes, load_cover_images, select_cover_image, get_s3_image_url
from app.tasks import generate_custom_recommendations, generate_entertainment_recommendations
from app.tasks.utils import EntertainmentType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Define the Provider enum
class Provider(str, Enum):
    GROQ = "groq"
    OPENAI = "openai"
    GOOGLE = "google"

# Define the Recommendation model
class RecommendationRequest(BaseModel):
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    provider: Provider = Provider.GROQ
    model: str = "llama-3.1-8b-instant"
    archetypes: Optional[str] = None
    keywords: Optional[str] = None
    max_recommendations: int = 5
    user_prompt: Optional[str] = None
    neighborhood: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class RecommendationResponse(BaseModel):
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

google_client = genai.Client(
    api_key=settings.google_api_key.get_secret_value()
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

global_archetypes = [
    "adventurer", "nature-lover", "urban-culture", "cultural-explorer",
    "lifestyle", "photographer", "minimalist", "ocean-lover",
    "food-traveler", "fitness", "wellness", "animal-lover",
    "art-aficionado", "science-enthusiast", "family-oriented",
    "bohemian", "sunset-chaser", "work-motivated", "festival-goer",
    "fashion-enthusiast", "landscape-enthusiast", "luxury-lover",
    "teen", "young", "adult", "senior", "daytime", "nighttime",
    "sociable", "solitary"
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
                "enum": keywords + global_archetypes
            }
        },
        "required": ["category", "prompt", "searchQuery", "usedArchetypes", "usedKeywords", "recommendedImage"]
    }
}

# Initialize geocoder
geocoder = Nominatim(user_agent="genie-backend")

@router.post("/generate")
async def generate_recommendations(
    request: RecommendationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        if request.time_of_day and request.time_of_day in ["morning", "afternoon", "evening", "night"]:
            generate_custom_recommendations.delay(
                user_id=current_user["uid"],
                neighborhood=request.neighborhood,
                latitude=request.latitude,
                longitude=request.longitude,
                time_of_day=request.time_of_day,
            )

            generate_entertainment_recommendations.delay(
                user_id=current_user["uid"],
                entertainment_type=EntertainmentType.MOVIES,
            )

            generate_entertainment_recommendations.delay(
                user_id=current_user["uid"],
                entertainment_type=EntertainmentType.TV_SHOWS,
            )

            return Response(status_code=status.HTTP_204_NO_CONTENT)
        elif request.user_prompt and request.archetypes and request.keywords:
            await generate_recommendations_legacy(request)
        else:
            raise HTTPException(status_code=400, detail="Invalid request")
            
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/generate-legacy")
async def generate_recommendations_legacy(
    request: RecommendationRequest
):
    try:
        # Select the appropriate client based on provider
        if request.provider == Provider.GROQ:
            client = groq_client
        elif request.provider == Provider.OPENAI:
            client = openai_client
        elif request.provider == Provider.GOOGLE:
            client = google_client
        else:
            raise HTTPException(status_code=400, detail="Invalid provider specified")

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

            return [RecommendationResponse(id=str(uuid.uuid4()), **rec) for rec in recommendations]
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

                return [RecommendationResponse(id=str(uuid.uuid4()), **rec) for rec in processed_recommendations]
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_recommendations_for_user_request(
    client: Union[AsyncOpenAI, genai.Client],
    location: str,
    archetypes: str,
    keywords: str,
    user_request: str,
    max_recommendations: int = 3,
    model: str = "gpt-4o-mini"
) -> List[dict]:
    """
    Generate recommendations for a user's request with improved efficiency and reliability.
    
    Args:
        client: The AI client to use (OpenAI, Groq, or Google)
        location: The location to search in
        archetypes: User's travel archetypes
        keywords: User's interests
        user_request: Specific user request
        max_recommendations: Maximum number of recommendations to generate
        model: The model to use for generation
        
    Returns:
        List of unique and validated recommendations
    """
    # Build the prompt with clear instructions for uniqueness and validation
    llm_prompt = f"""
    Generate up to {max_recommendations} highly relevant and diverse place recommendations based on the following criteria:

    Location: {location}
    Interests: {keywords}
    Archetypes: {archetypes}
    User request: {user_request}

    CRITICAL REQUIREMENTS:
    1. Each recommendation MUST be a unique, specific place (no duplicates)
    2. The searchQuery MUST be an exact place name that exists and can be found on Google Maps
    3. Each place must be relevant to the user's interests and archetypes
    4. If fewer than {max_recommendations} suitable places exist, return only the valid ones
    5. Each recommendation must be in a different category from the recommendation_categories list
    6. The place must be currently open and operational
    7. The place must be within 50 miles of the {location} area
    8. the recommendedImage MUST be a valid archetype or keyword related to the category of the recommendation. If you are talking about a restaurant, the recommendedImage should be related to restaurants or eating out. If you are talking about a coffee shop, the recommendedImage should be related to coffee shops.
    9. You MUST use a value from recommendedImage enum list.

    Example format for searchQuery:
    ✓ "Cafe Nola Frederick" (specific place)
    ✗ "cafes in Frederick" (too general)
    ✓ "Baker Park Frederick" (specific place)
    ✗ "parks near Frederick" (too general)
    """

    # Handle different client types
    if isinstance(client, genai.Client):
        response = await client.aio.models.generate_content(
            model=model,
            contents=llm_prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=SYSTEM_PROMPT
            )
        )
        recommendations = json.loads(response.text)
    else:
        # OpenAI/Groq client handling
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": llm_prompt}
            ],
            functions=[FUNCTION_SCHEMA],
            function_call={"name": "generate_recommendation"},
            temperature=0.6,
            n=max_recommendations
        )
        
        # Process and validate recommendations
        recommendations = []
        seen_places = set()  # Track unique places
        
        for choice in response.choices:
            if not choice.message.function_call:
                continue
                
            recommendation = json.loads(choice.message.function_call.arguments)
            
            # Skip if we've already seen this place
            if recommendation["searchQuery"] in seen_places:
                continue
                
            # Validate the recommendation
            if not all([
                recommendation["category"] in recommendation_categories,
                recommendation["searchQuery"],
                recommendation["usedArchetypes"],
                recommendation["usedKeywords"],
                recommendation["recommendedImage"]
            ]):
                continue
                
            # Add to seen places and recommendations
            seen_places.add(recommendation["searchQuery"])
            recommendations.append(recommendation)
            
            # If we have enough unique recommendations, stop
            if len(recommendations) >= max_recommendations:
                break
    
    # If we couldn't generate enough recommendations, log it but return what we have
    if len(recommendations) < max_recommendations:
        logger.info(f"Generated {len(recommendations)} recommendations instead of requested {max_recommendations}")
    
    return recommendations

async def generate_batch_recommendations(
    client: Union[AsyncOpenAI, genai.Client],
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
    5. The place must be within 50 miles of the {location} area
    6. the recommendedImage MUST be a valid archetype or keyword related to the category. If you are talking about a restaurant, the recommendedImage should be related to restaurants or eating out. If you are talking about a coffee shop, the recommendedImage should be related to coffee shops.
    7. You MUST use a value from recommendedImage enum list.

    Example format for searchQuery:
    ✓ "Cafe Nola Frederick" (specific place)
    ✗ "cafes in Frederick" (too general)
    ✓ "Baker Park Frederick" (specific place)
    ✗ "parks near Frederick" (too general)
    """
    
    # Handle different client types
    if isinstance(client, genai.Client):
        response = await client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=SYSTEM_PROMPT
            )
        )
        recommendations = [json.loads(response.text)]
    else:
        # OpenAI/Groq client handling
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            functions=[FUNCTION_SCHEMA],
            function_call={"name": "generate_recommendation"},
            temperature=0.6,
            n=1
        )
        
        recommendations = [
            json.loads(choice.message.function_call.arguments)
            for choice in response.choices
            if choice.message.function_call
        ]
    
    return recommendations

async def generate_friend_portal_recommendations(
    client: Union[AsyncOpenAI, genai.Client],
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
    All right, travel partner—let's line up a handful of spots around {location} that will feel perfectly "us."
    I'll serve up to **{max_recommendations}** ideas, each chosen with your shared archetypes ({archetypes}) in mind, so you and {friend_name} can settle in, swap stories, and enjoy the place itself rather than fuss over the planning.

    For every suggestion I'll make sure to:
    1. Pick a single, exact place or activity in {location} (no vague "best cafés nearby" stuff).
    2. Gently point out why it matches what the two of you typically gravitate toward—letting the place's vibe and details do the convincing.
    3. Add the practical bits you'll actually need: neighborhood, ideal time to go, a tip on what makes it stand out, and why it's an easy meet‑up spot.

    **Extra details I'll tuck into each entry**
    - **Title** – short and clear.
    - **Opening line** – a quick note on how the spot fits both of you (I'll skip using your name, mention {friend_name} once, and stick to second‑person everywhere else).
    - **Personalized note** – a friendly aside connecting the pick to your shared archetypes, without claiming to read your mind.
    - **TOP 3 KEYWORDS** – chosen from: {", ".join(keywords[:20])}.
    - **TOP 3 ARCHETYPES** – pulled from {archetypes}.
    - **image** – just the single archetype or keyword that best sums up the recommendation and is on the list of keywords and archetypes.

    I'll return everything in **pure JSON**—nothing else—using this structure (watch those commas and quotes!):

    {{
    "recommendations": [
        {{
        "title": "Name of Recommendation",
        "description": "Why this fits both of you, including subtle nods to shared interests and why it's an inviting place to meet",
        "practical_tips": "Neighborhood, hours, best time, standout feature, and why it's an easy rendezvous spot",
        "searchQuery": "Exact Place Name",
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "archetypes": ["archetype1", "archetype2", "archetype3"],
        "image": "most_relevant_term"
        }}
    ]
    }}

    I'll keep the list varied—no wall‑to‑wall restaurants or all museums—and true to {location}'s character.
    And remember: **only the JSON comes back to you.**

    IMPORTANT:
    - image most releavent term from the keywords and archetypes list: {", ".join(keywords + global_archetypes)}
    - searchQuery must be an exact place name that exists and can be found on Google Places API and must be within 50 miles of the {location} area
    """

    # Handle different client types
    if isinstance(client, genai.Client):
        response = await client.aio.models.generate_content(
            model=model,
            contents=llm_prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=SYSTEM_PROMPT
            )
        )
        return json.loads(response.text)
    else:
        # OpenAI/Groq client handling
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
    skip: int = Query(0, ge=0, description="Number of records to skip")
    limit: int = Query(15, ge=1, le=15, description="Number of records to return")

class PaginatedRecommendationResponse(BaseModel):
    recommendations: List[dict]
    total: int
    skip: int
    limit: int

@router.post("/friends/{friend_id}/portal", response_model=PaginatedRecommendationResponse)
async def get_friend_portal_recommendations(
    friend_id: str,
    request: FriendPortalRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user["uid"] == friend_id:
        raise HTTPException(status_code=403, detail="You cannot access your own portal through this endpoint")
    
    user = await get_user_by_id(db, current_user["uid"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    friend = await get_user_by_id(db, friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    
    # check if user.archetypes is a list and not empty
    if not isinstance(user.archetypes, list) or not user.archetypes:
        raise HTTPException(status_code=400, detail="User archetypes not found")
    
    # check if friend.archetypes is a list and not empty
    if not isinstance(friend.archetypes, list) or not friend.archetypes:
        raise HTTPException(status_code=400, detail="Friend archetypes not found")
    
    try:
        # Get total count of recommendations
        count_query = (
            select(func.count())
            .select_from(UserRecommendation)
            .where(UserRecommendation.user_id == friend_id)
        )
        total_count = await db.scalar(count_query)

        # Extract recommendations from UserRecommendation table with eager loading
        query = (
            select(UserRecommendation)
            .options(selectinload(UserRecommendation.recommendation))
            .where(UserRecommendation.user_id == friend_id)
            .order_by(UserRecommendation.created_at.desc())  # Order by creation date, newest first
            .offset(request.skip)
            .limit(request.limit)
        )
        result = await db.execute(query)
        user_recommendations = result.scalars().all()
        
        recommendations = []
        for user_recommendation in user_recommendations:
            if not user_recommendation.recommendation:  # Skip if recommendation is None
                continue
                
            # Safely get place_details description
            place_details = user_recommendation.recommendation.place_details or {}
            practical_tips = place_details.get("description", "")
            
            recommendation = {
                "title": user_recommendation.recommendation.search_query,
                "category": user_recommendation.recommendation.category,
                "description": user_recommendation.recommendation.prompt,
                "practical_tips": practical_tips,
                "searchQuery": user_recommendation.recommendation.search_query,
                "keywords": user_recommendation.recommendation.keywords or [],
                "archetypes": user_recommendation.recommendation.archetypes or [],
                "image": user_recommendation.recommendation.image_url,
                "placeDetails": user_recommendation.recommendation.place_details,
                "resourceDetails": user_recommendation.recommendation.resource_details,
                "created_at": user_recommendation.created_at.isoformat() if user_recommendation.created_at else None,
            }
            recommendations.append(recommendation)

        return {
            "recommendations": recommendations,
            "total": total_count,
            "skip": request.skip,
            "limit": request.limit
        }
    except Exception as e:
        logger.error(f"Error finding common archetypes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _build_base_query(user_id: str, category_filter: List[str]) -> Select:
    """Build base query for recommendations with common fields."""
    return (
        select(
            UserRecommendation.id.label('user_rec_id'),
            Recommendation.id,
            Recommendation.category,
            Recommendation.prompt,
            Recommendation.search_query,
            Recommendation.place_details,
            Recommendation.archetypes,
            Recommendation.keywords,
            Recommendation.image_url,
            Recommendation.location_geom,
            Recommendation.resource_details,
            null().label('distance'),
            UserRecommendation.created_at.label('created_at')
        )
        .join(Recommendation, UserRecommendation.recommendation_id == Recommendation.id)
        .where(
            UserRecommendation.user_id == user_id,
            UserRecommendation.is_seen == False,
            Recommendation.category.in_(category_filter)
        )
    )

def _build_entertainment_query(user_id: str) -> Select:
    """Build query for entertainment recommendations."""
    return _build_base_query(user_id, ["movies", "tv_shows"])

def _build_location_query(user_id: str, latitude: Optional[float], longitude: Optional[float], radius_km: float) -> Select:
    """Build query for location-based recommendations with optional spatial filtering."""
    query = (
        select(
            UserRecommendation.id.label('user_rec_id'),
            Recommendation.id,
            Recommendation.category,
            Recommendation.prompt,
            Recommendation.search_query,
            Recommendation.place_details,
            Recommendation.archetypes,
            Recommendation.keywords,
            Recommendation.image_url,
            Recommendation.location_geom,
            Recommendation.resource_details,
            null().label('distance'),
            UserRecommendation.created_at.label('created_at')
        )
        .join(Recommendation, UserRecommendation.recommendation_id == Recommendation.id)
        .where(
            UserRecommendation.user_id == user_id,
            UserRecommendation.is_seen == False,
            Recommendation.category.notin_(["movies", "tv_shows"])
        )
    )
    
    if latitude is not None and longitude is not None:
        point_wkt = f'SRID=4326;POINT({longitude} {latitude})'
        query = query.where(
            func.ST_DWithin(
                Recommendation.location_geom,
                func.ST_GeomFromEWKT(point_wkt),
                radius_km
            )
        )
        # Update distance calculation for filtered results
        query = query.with_only_columns(
            UserRecommendation.id.label('user_rec_id'),
            Recommendation.id,
            Recommendation.category,
            Recommendation.prompt,
            Recommendation.search_query,
            Recommendation.place_details,
            Recommendation.archetypes,
            Recommendation.keywords,
            Recommendation.image_url,
            Recommendation.location_geom,
            Recommendation.resource_details,
            func.ST_Distance(
                Recommendation.location_geom,
                func.ST_GeomFromEWKT(point_wkt)
            ).label('distance'),
            UserRecommendation.created_at.label('created_at')
        )
    
    return query

def _process_recommendation_row(row) -> dict:
    """Process a single recommendation row into a dictionary."""
    user_rec_id, rec_id, category, prompt, search_query, place_details, archetypes, keywords, image_url, location_geom, resource_details, distance, created_at = row
    
    recommendation_data = {
        "id": rec_id,
        "category": category,
        "prompt": prompt,
        "searchQuery": search_query,
        "placeDetails": place_details,
        "recommendedImage": image_url,
        "usedArchetypes": archetypes,
        "usedKeywords": keywords,
        "resourceDetails": resource_details,
        "created_at": created_at.isoformat() if created_at else None
    }
    
    if category not in ["movies", "tv_shows"] and distance is not None:
        recommendation_data["distance_km"] = round(distance / 1000, 2)
    
    return recommendation_data

def _interleave_recommendations(entertainment_recommendations: List[dict], location_recommendations: List[dict]) -> List[dict]:
    """Interleave entertainment and location recommendations."""
    recommendations = []
    max_length = max(len(location_recommendations), len(entertainment_recommendations))
    
    for i in range(max_length):
        if i < len(location_recommendations):
            recommendations.append(location_recommendations[i])
        if i < len(entertainment_recommendations):
            recommendations.append(entertainment_recommendations[i])
    
    return recommendations

@router.get("/user-recommendations", response_model=List[dict])
async def get_user_recommendations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(25, ge=1, le=100, description="Number of records to return"),
    latitude: Optional[float] = Query(None, ge=-90, le=90, description="Latitude in decimal degrees"),
    longitude: Optional[float] = Query(None, ge=-180, le=180, description="Longitude in decimal degrees"),
    radius_km: Optional[float] = Query(50.0, ge=0.1, le=50.0, description="Search radius in kilometers (max 50km)"),
    time_of_day: Optional[str] = Query(None, description="Filter recommendations by time of day (morning, afternoon, evening, night)"),
    neighborhood: Optional[str] = Query(None, description="Neighborhood name for location-based filtering"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # Validate coordinates
        if (latitude is None) != (longitude is None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both latitude and longitude must be provided together"
            )

        user_id = current_user["uid"]
        has_coordinates = latitude is not None and longitude is not None

        # Build queries
        entertainment_query = _build_entertainment_query(user_id)
        logger.info(f"Entertainment query: {entertainment_query}")
        logger.info(f"Has coordinates: {has_coordinates}")
        logger.info(f"Latitude: {latitude}")
        logger.info(f"Longitude: {longitude}")
        logger.info(f"Radius: {radius_km}")

        # Execute appropriate query based on coordinates
        if has_coordinates:
            logger.info(f"Building location query for user {user_id} with coordinates {latitude}, {longitude} and radius {radius_km}")
            location_query = _build_location_query(user_id, latitude, longitude, radius_km)
            compiled = location_query.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True}
            )
            logger.info(f"Location query: {compiled}")
            combined_query = entertainment_query.union_all(location_query).subquery()
            final_query = (
                select(combined_query)
                .order_by(combined_query.c.category.in_(["movies", "tv_shows"]).desc())
                .offset(skip)
                .limit(limit)
            )
        else:
            logger.info(f"Building entertainment query for user {user_id}")
            entertainment_subquery = entertainment_query.subquery()
            final_query = (
                select(entertainment_subquery)
                .order_by(entertainment_subquery.c.category.in_(["movies", "tv_shows"]).desc())
                .offset(skip)
                .limit(limit)
            )

        # Execute query and process results
        result = await db.execute(final_query)
        results = result.all()
        
        # Separate and process recommendations
        entertainment_recommendations = []
        location_recommendations = []
        
        for row in results:
            recommendation_data = _process_recommendation_row(row)
            if recommendation_data["category"] in ["movies", "tv_shows"]:
                entertainment_recommendations.append(recommendation_data)
            else:
                location_recommendations.append(recommendation_data)
        
        logger.info(f"Entertainment recommendations: {entertainment_recommendations}")
        logger.info(f"Location recommendations: {location_recommendations}")
        
        # Trigger generation if no location recommendations found
        if not location_recommendations and has_coordinates:
            logger.info(f"No location recommendations found for user {user_id}, triggering custom recommendations generation for {neighborhood} with coordinates {latitude}, {longitude} and time of day {time_of_day}")
            generate_custom_recommendations.delay(
                user_id=user_id,
                neighborhood=neighborhood,
                latitude=latitude,
                longitude=longitude,
                time_of_day=time_of_day or "afternoon",
            )
        
        # Shuffle and interleave recommendations
        random.shuffle(entertainment_recommendations)
        random.shuffle(location_recommendations)
        
        return _interleave_recommendations(entertainment_recommendations, location_recommendations)
        
    except Exception as e:
        logger.error(f"Error fetching user recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{recommendation_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_recommendation_seen(
    recommendation_id: int = Path(..., description="The ID of the recommendation to mark as seen"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a recommendation as seen for the current user.
    
    Args:
        recommendation_id: ID of the recommendation to mark as seen
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        None
        
    Raises:
        HTTPException: If recommendation not found or update fails
    """
    try:
        # Update the UserRecommendation record
        query = (
            update(UserRecommendation)
            .where(
                UserRecommendation.recommendation_id == recommendation_id,
                UserRecommendation.user_id == current_user["uid"],
                UserRecommendation.is_seen == False,
                UserRecommendation.is_seen == False  # Only update if not already seen
            )
            .values(
                is_seen=True,
                seen_at=datetime.now(timezone.utc)
            )
        )
        
        result = await db.execute(query)
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found or already seen"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error marking recommendation as seen: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
