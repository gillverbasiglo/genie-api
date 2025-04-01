# places_routes.py
import httpx
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.common import get_current_user
from ..config import settings


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/googlePlaces", tags=["googlePlaces"])

API_KEY = settings.google_api_key.get_secret_value()

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
    open_now: Optional[bool] = Field(alias="openNow", serialization_alias="open_now", default=None)
    periods: Optional[List[PlaceOpeningHoursPeriod]] = Field(alias="periods", serialization_alias="periods", default=None)
    weekday_text: Optional[List[str]] = Field(alias="weekdayDescriptions", serialization_alias="weekday_text", default=None)
    secondary_hours: Optional[List[Dict[str, Any]]] = Field(alias="secondaryHours", serialization_alias="secondary_hours", default=None)
    type: Optional[str] = Field(alias="type", serialization_alias="type", default=None)

class PlusCode(BaseModel):
    global_code: Optional[str] = Field(alias="globalCode", serialization_alias="global_code", default=None)
    compound_code: Optional[str] = Field(alias="compoundCode", serialization_alias="compound_code", default=None)

class AddressComponent(BaseModel):
    long_name: str
    short_name: str
    types: List[str]

class AuthorAttribution(BaseModel):
    display_name: Optional[str] = None
    uri: Optional[str] = None
    photo_uri: Optional[str] = Field(alias="photoUri", serialization_alias="photo_uri", default=None)

class Photo(BaseModel):
    name: str
    width_px: Optional[int] = Field(alias="widthPx", serialization_alias="width_px", default=None)
    height_px: Optional[int] = Field(alias="heightPx", serialization_alias="height_px", default=None)
    author_attribution: Optional[List[AuthorAttribution]] = Field(alias="authorAttributions", serialization_alias="author_attributions", default=None)

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

class DisplayName(BaseModel):
    text: str
    languageCode: Optional[str] = None

class Place(BaseModel):
    id: str
    display_name: DisplayName = Field(serialization_alias="display_name", alias="displayName")
    formatted_address: Optional[str] = Field(alias="formattedAddress", serialization_alias="formattedAddress", default=None)
    location: Optional[Location] = None
    viewport: Optional[Viewport] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = Field(alias="userRatingCount", serialization_alias="user_ratings_total", default=None)
    editorial_summary: Optional[Dict[str, str]] = Field(alias="editorialSummary", serialization_alias="editorial_summary", default=None)
    photos: Optional[List[Photo]] = None
    price_level: Optional[str] = Field(alias="priceLevel", serialization_alias="price_level", default=None)
    opening_hours: Optional[PlaceOpeningHours] = None
    website_uri: Optional[str] = Field(alias="websiteUri", serialization_alias="website_uri", default=None)
    icon_mask_base_uri: Optional[str] = Field(alias="iconMaskBaseUri", serialization_alias="icon_mask_base_uri", default=None)
    icon_background_color: Optional[str] = Field(alias="iconBackgroundColor", serialization_alias="icon_background_color", default=None)
    plus_code: Optional[PlusCode] = Field(alias="plusCode", serialization_alias="plus_code", default=None)
    current_opening_hours: Optional[PlaceOpeningHours] = Field(alias="currentOpeningHours", serialization_alias="current_opening_hours", default=None)
    secondary_opening_hours: Optional[List[PlaceOpeningHours]] = Field(alias="secondaryOpeningHours", serialization_alias="secondary_opening_hours", default=None)
    curbside_pickup: Optional[bool] = Field(alias="curbsidePickup", serialization_alias="curbside_pickup", default=None)
    delivery: Optional[bool] = Field(alias="delivery", serialization_alias="delivery", default=None)
    dine_in: Optional[bool] = Field(alias="dineIn", serialization_alias="dine_in", default=None)
    reservable: Optional[bool] = Field(alias="reservable", serialization_alias="reservable", default=None)
    serves_breakfast: Optional[bool] = Field(alias="servesBreakfast", serialization_alias="serves_breakfast", default=None)
    serves_lunch: Optional[bool] = Field(alias="servesLunch", serialization_alias="serves_lunch", default=None)
    serves_dinner: Optional[bool] = Field(alias="servesDinner", serialization_alias="serves_dinner", default=None)
    takeout: Optional[bool] = Field(alias="takeout", serialization_alias="takeout", default=None)
    serves_vegetarian_food: Optional[bool] = Field(alias="servesVegetarianFood", serialization_alias="serves_vegetarian_food", default=None)
    reviews: Optional[List[Review]] = None
    url: Optional[str] = None

    class Config:
        allow_population_by_alias = True
        # alias_generator = lambda x: x.replace('_', '')

class PlaceSearchRequest(BaseModel):
    query: str
    place_type: Optional[str] = None
    location: Optional[str] = None
    radius: float = 5000.0
    fields: str = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.editorialSummary,places.photos,places.priceLevel,places.websiteUri,places.iconMaskBaseUri,places.iconBackgroundColor,places.plusCode,places.currentOpeningHours,places.curbsidePickup,places.delivery,places.dineIn,places.reservable,places.servesBreakfast,places.servesLunch,places.servesDinner,places.takeout,places.servesVegetarianFood,places.reviews,places.userRatingCount"
    language_code: Optional[str] = None
    region_code: Optional[str] = None

class PlacesSearchResponse(BaseModel):
    places: List[Place]

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
@router.post("/search", response_model=PlacesSearchResponse, dependencies=[Depends(get_current_user)])
async def search_places(request: PlaceSearchRequest):
    logger.info(f"Searching places with query: '{request.query}'")
    
    # Prepare request body
    request_data = {
        "textQuery": request.query
    }
    
    # Add location bias if provided
    if request.location:
        try:
            # Assuming location is in format "lat,lng"
            lat, lng = map(float, request.location.split(','))
            request_data["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lng
                    },
                    "radius": request.radius  # 5km radius
                }
            }
        except:
            logger.warning(f"Invalid location format: {request.location}. Expected 'lat,lng'")
    
    # Add included type if provided
    if request.place_type:
        request_data["includedType"] = request.place_type
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/places:searchText"
            
            logger.debug(f"Making Places API request to: {url}")
            headers = get_auth_header()
            headers["Content-Type"] = "application/json"
            headers["X-Goog-FieldMask"] = request.fields
            
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
@router.get("/details/{place_id}", response_model=Place, dependencies=[Depends(get_current_user)])
async def get_place_details(place_id: str, fields: str = None):
    logger.debug(f"Fetching details for place ID: {place_id}")
    
    async with await get_client() as client:
        try:
            url = f"{BASE_URL}/places/{place_id}"
            
            params = {}
            if fields:
                params["fields"] = fields
            
            headers = get_auth_header()
            headers["X-Goog-FieldMask"] = "*"
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Place details request failed with status code: {response.status_code}, response: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            try:
                response_data = response.json()
                logger.debug(f"Place details data: {response_data}")
                
                # Add type checking before returning
                if not isinstance(response_data, dict):
                    logger.error(f"Unexpected response format: {response_data}")
                    raise HTTPException(status_code=500, detail="Invalid response format from Google Places API")
                
                logger.debug(f"Successfully processed details for {response_data.get('name', 'Unknown place')}")
                
                return response_data
                
            except ValueError as json_error:
                logger.error(f"JSON decode error: {str(json_error)}")
                raise HTTPException(status_code=500, detail="Failed to decode API response")
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in get_place_details: {str(e)}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

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
            headers["X-Goog-FieldMask"] = "*"
            
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
@router.get("/{place_id}/photos/{photo_name}", dependencies=[Depends(get_current_user)])
async def get_place_photo(photo_name: str, place_id: str, maxWidthPx: int = None, maxHeightPx: int = None, skipHttpRedirect: bool = True):
    logger.debug(f"Fetching photo with name: {photo_name}")
    
    # Create query parameters
    params = {}
    if maxWidthPx:
        params["maxWidthPx"] = maxWidthPx
    if maxHeightPx:
        params["maxHeightPx"] = maxHeightPx
    params["skipHttpRedirect"] = skipHttpRedirect
    async with await get_client() as client:
        try:
            # Use the v1 photos endpoint with the photo name
            url = f"{BASE_URL}/places/{place_id}/photos/{photo_name}/media"
            
            headers = get_auth_header()
            headers["X-Goog-FieldMask"] = "*"
            
            response = await client.get(url, params=params, headers=headers, follow_redirects=True)
            
            if response.status_code != 200:
                logger.error(f"Photo request failed with status code: {response.status_code}, response: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Error from Google Places API")
            
            response_data = response.json()

            # Return the photo content
            return response_data
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
