import httpx
import logging
from typing import Optional, List
from fastapi import HTTPException
from app.config import settings
from app.schemas.tripadvisor import (
    LocationCategory,
    RadiusUnit,
    TravelSearchResponse,
    TravelDestinationDetail,
    TravelPhotosResponse,
    Location,
    PhotoData
)

# Configure logging
logger = logging.getLogger(__name__)

API_KEY = settings.trip_advisor_api_key.get_secret_value()
BASE_URL = "https://api.content.tripadvisor.com/api/v1"

# HTTP client for making API requests
async def get_client():
    return httpx.AsyncClient(timeout=20.0)

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

async def get_location_details(location_id: str, language: str = "en", currency: str = "USD"):
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

async def get_location_photos(location_id: str, language: str = "en", limit: Optional[int] = None):
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
