from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Table, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from datetime import datetime, timezone
from geoalchemy2 import Geometry

from app.database import Base

# Define enum values for location event types
LOCATION_EVENT_TYPES = ["location_update", "visited_location"]

class Location(Base):
    __tablename__ = 'locations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)

    # Location details
    event_type = Column(Enum(*LOCATION_EVENT_TYPES, name="location_event_type"), nullable=False)
    event_data = Column(JSONB, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="locations")
