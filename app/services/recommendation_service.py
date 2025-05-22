import json
import httpx

from dataclasses import dataclass
from pydantic import BaseModel
from typing import Dict, Any, AsyncGenerator, Optional, List

from app.schemas.users import Archetype, Keyword
from app.config import settings
@dataclass
class Location:
    country: str
    city: str
    latitude: float
    longitude: float
    timezone: str

class GenieAIRequest(BaseModel):
    model: str
    group: str
    user_data: Dict[str, Any]

class StreamPart(BaseModel):
    type: str
    content: Dict[str, Any]

async def get_location_from_ip(ip_address: str) -> Optional[Location]:
    """
    Get location information from IP address using ipapi.co service.
    
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

async def stream_genie_recommendations(
    time_of_day: str,
    archetypes: Optional[List[Archetype]] = None,
    keywords: Optional[List[Keyword]] = None,
    location: Optional[str] = None,
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
    GENIE_AI_URL = settings.GENIE_AI_URL
    
    
    if ip_address:
        # Get location information from IP
        location = await get_location_from_ip(ip_address)
        print(location)
        # Create user data with location information
        user_data = {}
        if location:
            user_data.update({
                "location": f"{location.city}, {location.country}",
                "time_of_day": time_of_day
            })
    else:
        user_data = {
            "location": location,
            "time_of_day": time_of_day
        }

    if archetypes:
        user_data.update({
            "archetypes": archetypes
        })
    
    if keywords:
        user_data.update({
            "preferences": keywords
        })
    
    request_data = GenieAIRequest(
        model="genie-gemini",
        group="recommendations",
        user_data=user_data
    )
    
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "x-vercel-ai-data-stream": "v1"  # Required for Vercel AI SDK protocol
    }
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                GENIE_AI_URL,
                json=request_data.model_dump(),
                headers=headers,
                timeout=30.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if part := await parse_stream_part(line):
                        # Handle different types of stream parts
                        if part.type == "a":  # Tool result part
                            # Extract the structured output from the tool result
                            if "result" in part.content:
                                yield part.content["result"]
                        elif part.type == "3":  # Error part
                            raise Exception(f"AI Service Error: {part.content}")
                        # Add other part types as needed (text, reasoning, etc.)
        except httpx.HTTPError as e:
            # Log the error here if you have a logging system
            raise e
