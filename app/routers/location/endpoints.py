import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.common import get_current_user
from app.init_db import get_db
from app.models.location import Location
from app.schemas.location import LocationEventCreate, LocationEventResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/location", tags=["location"])

@router.post("/event", response_model=LocationEventResponse)
async def create_location_event(
    event_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new location event for the authenticated user.
    
    Args:
        event_data: JSON object containing event data with eventType key
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        LocationEventResponse: Created location event
        
    Raises:
        HTTPException: If eventType is missing or invalid
    """
    try:
        # Extract eventType from the JSON object (camelCase from mobile app)
        event_type = event_data.get("eventType")
        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="eventType is required in the request body"
            )
        
        # Validate event_type
        valid_event_types = ["location_update", "visited_location"]
        if event_type not in valid_event_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid eventType. Must be one of: {valid_event_types}"
            )
        
        # Validate required fields based on event type
        if event_type == "location_update":
            if not event_data.get("location"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="location object is required for location_update events"
                )
        elif event_type == "visited_location":
            if not event_data.get("location"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="location object is required for visited_location events"
                )
            # visitData is optional for visited_location events
        
        # Create new location event
        # Store the complete JSON payload in event_data
        # Convert camelCase eventType to snake_case event_type for database
        location_event = Location(
            user_id=current_user["uid"],
            event_type=event_type,  # This is already snake_case from validation
            event_data=event_data   # Store complete JSON payload
        )
        
        # Add to database
        db.add(location_event)
        await db.commit()
        await db.refresh(location_event)
        
        logger.info(f"Created location event for user {current_user['uid']}: {event_type}")
        
        return location_event
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating location event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create location event: {str(e)}"
        )

@router.get("/events", response_model=list[LocationEventResponse])
async def get_location_events(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get location events for the authenticated user.
    
    Args:
        skip: Number of events to skip (for pagination)
        limit: Maximum number of events to return
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        List of location events for the user
    """
    try:
        query = select(Location).where(
            Location.user_id == current_user["uid"]
        ).order_by(
            Location.created_at.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        events = result.scalars().all()
        
        logger.info(f"Retrieved {len(events)} location events for user {current_user['uid']}")
        
        return events
        
    except Exception as e:
        logger.error(f"Error retrieving location events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve location events: {str(e)}"
        )