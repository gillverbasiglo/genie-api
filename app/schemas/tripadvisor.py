from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


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