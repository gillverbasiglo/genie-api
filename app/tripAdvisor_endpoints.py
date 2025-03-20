# tripadvisor_routes.py

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import httpx
import logging
from enum import Enum
import os
from dotenv import load_dotenv
from .secrets_manager import SecretsManager
from .config import Settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/tripadvisor", tags=["tripadvisor"])


settings = Settings()
secrets = SecretsManager(region_name=settings.aws_region)

# Get API key from AWS Secrets Manager like we did in the main.py file for groq
API_KEY = secrets.get_api_key("tripAdvisor")
BASE_URL = "https://api.content.tripadvisor.com/api/v1"

# Enum definitions
class LocationCategory(str, Enum):
    hotels = "hotels"
    attractions = "attractions"
    restaurants = "restaurants"
    geos = "geos"

class RadiusUnit(str, Enum):
    kilometers = "km"
    miles = "mi"
    meters = "m"

# Models for API response validation
class Location(BaseModel):
    location_id: str = Field(..., alias="location_id")
    name: str
    address_obj: Optional[dict] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
class TravelSearchResponse(BaseModel):
    data: List[Location]
    
class TravelDestinationDetail(BaseModel):
    location_id: str
    name: str
    description: Optional[str] = None
    # Add other fields based on actual API response
    
class PhotoData(BaseModel):
    id: int
    caption: Optional[str] = None
    images: dict
    
class TravelPhotosResponse(BaseModel):
    data: List[PhotoData]

# HTTP client for making API requests
async def get_client():
    return httpx.AsyncClient(timeout=20.0)

# Endpoint for location search
@router.get("/location/search", response_model=TravelSearchResponse)
async def search_locations(
    search_query: str,
    category: Optional[LocationCategory] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    lat_long: Optional[str] = None,
    radius: Optional[int] = None,
    radius_unit: Optional[RadiusUnit] = None,
    language: str = "en"
):
    logger.info(f"Searching locations with query: '{search_query}'")
    
    # Construct query parameters
    params = {
        "key": API_KEY,
        "searchQuery": search_query,
        "language": language
    }
    
    # Add optional parameters if provided
    if category:
        params["category"] = category.value
    if phone:
        params["phone"] = phone
    if address:
        params["address"] = address
    if lat_long:
        params["latLong"] = lat_long
    if radius:
        params["radius"] = str(radius)
    if radius_unit:
        params["radiusUnit"] = radius_unit.value
    
    # Make request to TripAdvisor API
    async with await get_client() as client:
        try:
            logger.debug(f"Making TripAdvisor API request to: {BASE_URL}/location/search")
            response = await client.get(f"{BASE_URL}/location/search", params=params)
            
            if response.status_code != 200:
                logger.error(f"TripAdvisor API request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from TripAdvisor API")
            
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Endpoint for location details
@router.get("/location/{location_id}/details", response_model=TravelDestinationDetail)
async def get_location_details(
    location_id: str,
    language: str = "en",
    currency: str = "USD"
):
    logger.debug(f"Fetching details for location ID: {location_id}")
    
    params = {
        "key": API_KEY,
        "language": language,
        "currency": currency
    }
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/location/{location_id}/details"
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Location details request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from TripAdvisor API")
            
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to decode location details: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing response: {str(e)}")

# Endpoint for location photos
@router.get("/location/{location_id}/photos", response_model=TravelPhotosResponse)
async def get_location_photos(
    location_id: str,
    language: str = "en",
    limit: Optional[int] = None
):
    logger.debug(f"Fetching photos for location ID: {location_id}")
    
    params = {
        "key": API_KEY,
        "language": language
    }
    
    if limit:
        params["limit"] = str(limit)
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/location/{location_id}/photos"
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Location photos request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from TripAdvisor API")
            
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to decode location photos: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing response: {str(e)}")

# Convenience endpoints
@router.get("/hotels/{location}", response_model=TravelSearchResponse)
async def search_hotels(location: str):
    return await search_locations(search_query=location, category=LocationCategory.hotels)

@router.get("/attractions/{location}", response_model=TravelSearchResponse)
async def search_attractions(location: str):
    return await search_locations(search_query=location, category=LocationCategory.attractions)

@router.get("/restaurants/{location}", response_model=TravelSearchResponse)
async def search_restaurants(location: str):
    return await search_locations(search_query=location, category=LocationCategory.restaurants)

@router.get("/nearby", response_model=TravelSearchResponse)
async def search_nearby(
    query: str,
    latitude: float,
    longitude: float,
    radius: int = 5000,
    unit: RadiusUnit = RadiusUnit.meters,
    category: Optional[LocationCategory] = None
):
    lat_long = f"{latitude},{longitude}"
    return await search_locations(
        search_query=query,
        category=category,
        lat_long=lat_long,
        radius=radius,
        radius_unit=unit
    )