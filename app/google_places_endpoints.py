# places_routes.py
import httpx
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

from .common import get_current_user
from .config import Settings
from .secrets_manager import SecretsManager


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/googlePlaces", tags=["googlePlaces"])

settings = Settings()
secrets = SecretsManager(region_name=settings.aws_region)

API_KEY = secrets.get_api_key("google")
BASE_URL = "https://places.googleapis.com/v1"  # Updated base URL for Places API v1

# Models for response validation
class Location(BaseModel):
    latitude: float
    longitude: float

class Viewport(BaseModel):
    low: Location
    high: Location

class LocationRestriction(BaseModel):
    circle: Optional[Dict[str, Any]] = None
    rectangle: Optional[Dict[str, Any]] = None

class TextQuery(BaseModel):
    text: str
    language_code: Optional[str] = None

class PlaceOpeningHoursPeriod(BaseModel):
    open: Dict[str, Any]
    close: Optional[Dict[str, Any]] = None

class PlaceOpeningHours(BaseModel):
    open_now: Optional[bool] = None
    periods: Optional[List[PlaceOpeningHoursPeriod]] = None
    weekday_text: Optional[List[str]] = None
    secondary_hours: Optional[List[Dict[str, Any]]] = None
    type: Optional[str] = None

class PlusCode(BaseModel):
    global_code: Optional[str] = None
    compound_code: Optional[str] = None

class AddressComponent(BaseModel):
    long_name: str
    short_name: str
    types: List[str]

class AuthorAttribution(BaseModel):
    display_name: Optional[str] = None
    uri: Optional[str] = None
    photo_uri: Optional[str] = None

class Photo(BaseModel):
    name: str
    width_px: int
    height_px: int
    reference: Optional[str] = None
    author_attribution: Optional[AuthorAttribution] = None

class Review(BaseModel):
    name: Optional[str] = None
    author_name: Optional[str] = None
    rating: Optional[int] = None
    relative_time_description: Optional[str] = None
    time: Optional[str] = None
    text: Optional[Dict[str, Any]] = None
    author_photo: Optional[Dict[str, Any]] = None

class PriceLevel(BaseModel):
    level: Optional[int] = None
    price_range: Optional[str] = None

class Place(BaseModel):
    name: str
    id: str
    types: Optional[List[str]] = None
    national_phone_number: Optional[str] = None
    international_phone_number: Optional[str] = None
    formatted_address: Optional[str] = None
    address_components: Optional[List[AddressComponent]] = None
    location: Optional[Location] = None
    viewport: Optional[Viewport] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    editorial_summary: Optional[Dict[str, str]] = None
    photos: Optional[List[Photo]] = None
    price_level: Optional[PriceLevel] = None
    opening_hours: Optional[PlaceOpeningHours] = None
    website_uri: Optional[str] = None
    icon_mask_base_uri: Optional[str] = None
    icon_background_color: Optional[str] = None
    plus_code: Optional[PlusCode] = None
    current_opening_hours: Optional[PlaceOpeningHours] = None
    secondary_opening_hours: Optional[List[PlaceOpeningHours]] = None
    curbside_pickup: Optional[bool] = None
    delivery: Optional[bool] = None
    dine_in: Optional[bool] = None
    reservable: Optional[bool] = None
    serves_breakfast: Optional[bool] = None
    serves_lunch: Optional[bool] = None
    serves_dinner: Optional[bool] = None
    takeout: Optional[bool] = None
    serves_vegetarian_food: Optional[bool] = None
    reviews: Optional[List[Review]] = None
    url: Optional[str] = None

class PlaceSearchRequest(BaseModel):
    text_query: TextQuery
    location_bias: Optional[LocationRestriction] = None
    included_type: Optional[str] = None
    language_code: Optional[str] = None
    region_code: Optional[str] = None

class PlacesSearchResponse(BaseModel):
    places: List[Place]

class PlaceDetailsResponse(BaseModel):
    place: Place

class MediaMetadata(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None

class PhotoResponse(BaseModel):
    media: Optional[bytes] = None
    media_metadata: Optional[MediaMetadata] = None

# HTTP client for making API requests
async def get_client():
    return httpx.AsyncClient(timeout=30.0)

# Helper function to get API key header
def get_auth_header():
    return {"X-Goog-Api-Key": API_KEY}

# Endpoint for places search
@router.get("/search", response_model=PlacesSearchResponse, dependencies=[Depends(get_current_user)])
async def search_places(query: str, place_type: str = None, location: str = None):
    logger.info(f"Searching places with query: '{query}'")
    
    # Prepare request body
    request_data = {
        "textQuery": query
    }
    
    # Add location bias if provided
    if location:
        try:
            # Assuming location is in format "lat,lng"
            lat, lng = map(float, location.split(','))
            request_data["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lng
                    },
                    "radius": 5000.0  # 5km radius
                }
            }
        except:
            logger.warning(f"Invalid location format: {location}. Expected 'lat,lng'")
    
    # Add included type if provided
    if place_type:
        request_data["includedType"] = place_type
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/places:searchText"
            
            logger.debug(f"Making Places API request to: {url}")
            headers = get_auth_header()
            headers["Content-Type"] = "application/json"
            
            response = await client.post(url, json=request_data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Places API request failed with status code: {response.status_code}, response: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            logger.debug("Decoding places API response")
            response_data = response.json()
            logger.debug(f"Response data: {response_data}")
            
            # Transform response to match our model
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Endpoint for places details
@router.get("/details/{place_id}", response_model=PlaceDetailsResponse, dependencies=[Depends(get_current_user)])
async def get_place_details(place_id: str, fields: str = None):
    logger.debug(f"Fetching details for place ID: {place_id}")
    
    async with await get_client() as client:
        try:
            # Build URL with place ID
            url = f"{BASE_URL}/places/{place_id}"
            
            # Add fields parameter if provided
            params = {}
            if fields:
                params["fields"] = fields
            
            headers = get_auth_header()
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Place details request failed with status code: {response.status_code}, response: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            response_data = response.json()
            logger.debug(f"Place details data: {response_data}")
            
            logger.debug(f"Successfully processed details for {response_data.get('name', 'Unknown place')}")
            
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Endpoint for raw place details response
@router.get("/raw-details/{place_id}", dependencies=[Depends(get_current_user)])
async def get_place_details_raw(place_id: str, fields: str = None):
    logger.debug(f"Fetching raw details for place ID: {place_id}")
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/places/{place_id}"
            
            # Add fields parameter if provided
            params = {}
            if fields:
                params["fields"] = fields
            
            headers = get_auth_header()
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Place details request failed with status code: {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            # Return the raw JSON response
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

# Updated endpoint for photos using new v1 API
@router.get("/photos/{photo_name}", dependencies=[Depends(get_current_user)])
async def get_place_photo(photo_name: str, max_width_px: int = None, max_height_px: int = None):
    logger.debug(f"Fetching photo with name: {photo_name}")
    
    # Create query parameters
    params = {}
    if max_width_px:
        params["maxWidthPx"] = max_width_px
    if max_height_px:
        params["maxHeightPx"] = max_height_px
    
    async with await get_client() as client:
        try:
            # Use the v1 photos endpoint with the photo name
            url = f"{BASE_URL}/{photo_name}/media"
            
            headers = get_auth_header()
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Photo request failed with status code: {response.status_code}, response: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            response_data = response.json()

            # Return the photo content
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
