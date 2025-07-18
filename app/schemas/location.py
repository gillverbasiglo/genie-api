from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

class LocationEventType(str, Enum):
    """Enum for location event types."""
    LOCATION_UPDATE = "location_update"
    VISITED_LOCATION = "visited_location"

class LocationEventCreate(BaseModel):
    """Schema for creating a new location event."""
    event_type: LocationEventType = Field(..., description="Type of location event")
    event_data: Dict[str, Any] = Field(..., description="Event data as JSON object")

class LocationEventResponse(BaseModel):
    """Schema for location event response."""
    id: int
    user_id: str
    event_type: str
    event_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 