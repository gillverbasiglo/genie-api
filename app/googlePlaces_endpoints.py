# places_routes.py

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import httpx
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/places", tags=["places"])

# API configuration for testing purposes
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "AIzaSyBvCs3qRElCb82VSo6rYBwLCDQ7xPP8Pm8")
BASE_URL = "https://maps.googleapis.com/maps/api/place"

# Models for response validation
class Geometry(BaseModel):
    location: Dict[str, float]
    viewport: Optional[Dict[str, Dict[str, float]]] = None

class PlaceCandidate(BaseModel):
    place_id: str
    name: Optional[str] = None
    geometry: Optional[Geometry] = None

class PlaceSearchResponse(BaseModel):
    candidates: List[PlaceCandidate] = []
    status: str

class PlacePhoto(BaseModel):
    height: int
    width: int
    html_attributions: List[str]
    photo_reference: str

class OpeningHours(BaseModel):
    open_now: Optional[bool] = None
    periods: Optional[List[Dict[str, Any]]] = None
    weekday_text: Optional[List[str]] = None

class PlaceDetails(BaseModel):
    place_id: str
    name: str
    formatted_address: Optional[str] = None
    formatted_phone_number: Optional[str] = None
    geometry: Optional[Geometry] = None
    photos: Optional[List[PlacePhoto]] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    opening_hours: Optional[OpeningHours] = None
    website: Optional[str] = None
    price_level: Optional[int] = None
    types: Optional[List[str]] = None
    vicinity: Optional[str] = None

class PlaceDetailsResponse(BaseModel):
    result: Optional[PlaceDetails] = None
    status: str

# HTTP client for making API requests
async def get_client():
    return httpx.AsyncClient(timeout=30.0)

# Endpoint for places search
@router.get("/search", response_model=PlaceSearchResponse)
async def search_places(query: str, place_type: str, location: str):
    logger.info(f"Searching places with query: '{query}' in location: '{location}'")
    
    params = {
        "key": API_KEY,
        "input": f"{query} {place_type} in {location}",
        "inputtype": "textquery",
        "fields": "place_id,name,geometry"
    }
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/findplacefromtext/json"
            logger.debug(f"Making initial places API request to: {url}")
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Places API request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            logger.debug("Decoding places API response")
            response_data = response.json()
            print(response_data)
            
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Endpoint for places details
@router.get("/details/{place_id}", response_model=PlaceDetailsResponse)
async def get_place_details(place_id: str):
    logger.debug(f"Fetching details for place ID: {place_id}")
    
    params = {
        "key": API_KEY,
        "place_id": place_id
    }
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/details/json"
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Place details request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            response_data = response.json()
            print(f"Place details data: {response_data}")
            
            if "result" not in response_data:
                logger.error(f"No result found in place details response for place ID: {place_id}")
                raise HTTPException(status_code=404, detail="No result found in place details response")
            
            logger.debug(f"Successfully processed details for {response_data['result'].get('name', 'Unknown place')}")
            
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Endpoint for raw place details response. 
# I don't understand purpose of this call but we had this API call defined in Swift Places Service inside EventSearch Pakcage 
@router.get("/raw-details/{place_id}")
async def get_place_details_raw(place_id: str):
    logger.debug(f"Fetching raw details for place ID: {place_id}")
    
    params = {
        "key": API_KEY,
        "place_id": place_id
    }
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/details/json"
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Place details request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            # Return the raw JSON response
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")