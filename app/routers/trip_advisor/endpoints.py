# tripadvisor_routes.py
import httpx
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

from app.common import get_current_user
from app.config import settings
from app.schemas.tripadvisor import LocationCategory, RadiusUnit, TravelDestinationDetail, TravelPhotosResponse, TravelSearchResponse
from app.services.tripadvisor_service import get_location_details, get_location_photos, search_locations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/tripAdvisor", tags=["tripAdvisor"])


# Endpoint for location search
@router.get("/location/search", response_model=TravelSearchResponse, dependencies=[Depends(get_current_user)])
async def search_locations_api(
    search_query: str,
    category: Optional[LocationCategory] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    lat_long: Optional[str] = None,
    radius: Optional[int] = None,
    radius_unit: Optional[RadiusUnit] = None,
    language: str = "en"
):
    try:
        return await search_locations(
            search_query=search_query,
            category=category,
            phone=phone,
            address=address,
            lat_long=lat_long,
            radius=radius,
            radius_unit=radius_unit,
            language=language
        )
    except HTTPException as e:
        raise e

# Endpoint for location details
@router.get("/location/{location_id}/details", response_model=TravelDestinationDetail, dependencies=[Depends(get_current_user)])
async def get_location_details_api(
    location_id: str,
    language: str = "en",
    currency: str = "USD"
):
    try:
        return await get_location_details(location_id, language, currency)
    except HTTPException as e:
        raise e

# Endpoint for location photos
@router.get("/location/{location_id}/photos", response_model=TravelPhotosResponse, dependencies=[Depends(get_current_user)])
async def get_location_photos_api(
    location_id: str,
    language: str = "en",
    limit: Optional[int] = None
):
    try:
        return await get_location_photos(location_id, language, limit)
    except HTTPException as e:
        raise e

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

@router.get("/nearby", response_model=TravelSearchResponse, dependencies=[Depends(get_current_user)])
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
