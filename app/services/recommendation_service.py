import json
import httpx

from dataclasses import dataclass
from pydantic import BaseModel
from typing import Dict, Any, AsyncGenerator, Optional, List
from enum import Enum

from app.schemas.users import Archetype, Keyword
from app.config import settings

def generate_jwt_token_for_user(user_id: str, expires_in_hours: Optional[int] = 24) -> str:
    """
    Generate JWT token for user.
    
    Args:
        user_id: The user ID to include in the token
        expires_in_hours: Token expiration in hours. None for no expiration.
    
    Returns:
        JWT token string
    """
    import jwt
    from datetime import datetime, timedelta, timezone
    
    jwt_secret = settings.jwt_api_key.get_secret_value()

    payload = {
        "userId": user_id
    }
    
    # Add expiration if specified
    if expires_in_hours is not None:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    
    # Generate token
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    return token

class RecommendationType(str, Enum):
    PLACE = "place"
    MOVIE = "movie"
    MIXED = "mixed"

@dataclass
class Location:
    country: str
    city: str
    state: str
    latitude: float
    longitude: float
    timezone: str

class MessagePart(BaseModel):
    type: str
    text: str

class Message(BaseModel):
    role: str
    parts: List[MessagePart]

class GenieAIRequest(BaseModel):
    model: str
    group: str
    messages: List[Message]

class PlacesGenieAIRequest(GenieAIRequest):
    coordinates: Dict[str, Any]
    neighborhood: str

class GenieAIPortalRecommendationRequest(BaseModel):
    recommendationType: RecommendationType
    promptCount: int = 1
    parallelLimit: int = 1
    neighborhood: str
    city: str
    country: str
    coordinates: Dict[str, float]

class StreamPart(BaseModel):
    type: str
    content: Dict[str, Any]

async def get_location_from_ip(ip_address: str) -> Optional[Location]:
    """
    Get location information from the IP address using ipapi.co service.
    
    Args:
        ip_address: The IP address to look up
        
    Returns:
        Location object containing country, city, coordinates, and timezone
        Returns None if lookup fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://ipapi.co/{ip_address}/json/",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            return Location(
                country=data.get("country_name", ""),
                city=data.get("city", ""),
                state=data.get("region", ""),
                latitude=float(data.get("latitude", 0)),
                longitude=float(data.get("longitude", 0)),
                timezone=data.get("timezone", "")
            )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        # Log the error here if you have a logging system
        return None

async def parse_stream_part(line: str) -> Optional[StreamPart]:
    """
    Parse a stream part according to Vercel AI SDK protocol.
    Format: TYPE_ID:CONTENT_JSON\n
    """
    if not line.strip():
        return None
        
    try:
        type_id, content = line.split(':', 1)
        content_json = json.loads(content)
        return StreamPart(type=type_id, content=content_json)
    except (ValueError, json.JSONDecodeError):
        return None


async def _stream_genie_ai_request(
    request_data: GenieAIPortalRecommendationRequest,
    user_id: str,
    url: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generic function to handle HTTP streaming requests to Genie AI service.
    
    Args:
        request_data: The request payload to send
        user_id: User ID for JWT token generation
        url: Optional custom URL, defaults to settings.GENIE_AI_URL
        
    Yields:
        Dict containing structured output (tool results) from the AI response
        
    Raises:
        httpx.HTTPError: If the request fails
    """
    api_url = url or settings.GENIE_AI_URL
    bearer_token = generate_jwt_token_for_user(user_id)
    
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "x-vercel-ai-data-stream": "v1",
        "Authorization": f"Bearer {bearer_token}"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                api_url,
                json=request_data.model_dump(),
                headers=headers,
                timeout=30.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if part := await parse_stream_part(line):
                        if part.type == "a":  # Tool result part
                            if "result" in part.content and part.content["result"] is not None and "searches" not in part.content["result"]:
                                yield part.content["result"]
                        elif part.type == "3":  # Error part
                            raise Exception(f"AI Service Error: {part.content}")
        except httpx.HTTPError as e:
            raise e


async def stream_genie_recommendations(
    user_id: str,
    time_of_day: str,
    prompt: str,
    neighborhood: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    ip_address: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream recommendations from Genie AI service using Vercel AI SDK protocol.
    
    Args:
        ip_address: User's IP address for location-based recommendations
        
    Yields:
        Dict containing structured output (tool results) from the AI response
        
    Raises:
        httpx.HTTPError: If the request fails
    """
    if ip_address:
        # Get location information from IP
        location = await get_location_from_ip(ip_address)
        # Create a populated neighborhood, latitude, and longitude with location information
        neighborhood = location.state
        city = location.city
        country = location.country
        latitude = location.latitude
        longitude = location.longitude
    
    request_data = GenieAIPortalRecommendationRequest(
        recommendationType=RecommendationType.PLACE,
        neighborhood=neighborhood,
        city=city,
        country=country,
        coordinates={
            "latitude": latitude,
            "longitude": longitude
        }
    )

    # Use the generic stream handler
    async for result in _stream_genie_ai_request(request_data, user_id):
        yield result

async def stream_entertainment_recommendations(
    user_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream movie and TV show recommendations from Genie AI service using Vercel AI SDK protocol.
    
    Args:
        user_id: User ID
        
    Yields:
        Dict containing structured output (tool results) from the AI response with entertainment recommendations
        
    Raises:
        httpx.HTTPError: If the request fails
    """
    request_data = GenieAIPortalRecommendationRequest(
        recommendationType=RecommendationType.MOVIE,
        neighborhood="",
        city="",
        country="",
        coordinates={}
    )

    # Use the generic stream handler
    async for result in _stream_genie_ai_request(request_data, user_id):
        yield result
