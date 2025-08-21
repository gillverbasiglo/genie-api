# app/routers/mem0/endpoints.py
import logging
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.core.mem0.mem0_helpers import build_metadata
from app.core.mem0.mem0_manager import Mem0Manager
from app.core.mem0.memory_categories import MEM0_CATEGORIES
from app.init_db import get_db
from app.models.user import User
from app.services.mem0_service import MemoryService
from pydantic import BaseModel
from typing import Dict, Any, Optional


# Configure logging for this module
logger = logging.getLogger(__name__)

# Schema for storing user interactions
class UserInteractionData(BaseModel):
    """Data structure for storing user interactions"""
    query: str = Field(description="User's search query")
    location_data: Optional[Dict[str, Any]] = Field(default=None, description="Location information")
    model_used: Optional[str] = Field(default=None, description="LLM model used")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    additional_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

# Initialize router with prefix and tags for API documentation
router = APIRouter(prefix="/memories", tags=["memories"])

mem0_manager = Mem0Manager()

@router.post("/{user_id}/store_interaction")
async def store_user_interaction(
    user_id: str, 
    interaction_data: UserInteractionData
):
    try:
        logger.info(f"Storing user interaction for user {user_id}")

        result = await mem0_manager.store_user_interaction(
            user_id=user_id,
            query=interaction_data.query,
            location_data=interaction_data.location_data,
            model_used=interaction_data.model_used,
            session_id=interaction_data.session_id,
            additional_metadata=interaction_data.additional_metadata
        )

        if result:
            logger.info(f"Successfully stored user interaction for user {user_id}")
            return {
                "status": "success",
                "user_id": user_id,
                "memory_id": result.get("id", "unknown"),
                "message": "User interaction stored successfully"
            }
        else:
            logger.error(f"Failed to store user interaction for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to store user interaction")

    except Exception as e:
        logger.exception(f"Error storing user interaction for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error storing user interaction: {e}")
    

@router.post("/{user_id}/generate_memories")
async def generate_memories(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Generate and store new memories for a specific user.
    
    This endpoint triggers the memory generation process for a user, which involves:
    1. Retrieving user data and context
    2. Generating relevant memories using the MemoryService
    3. Storing the generated memories in the database
    
    Args:
        user_id (str): The unique identifier of the user for whom memories should be generated
        db (AsyncSession): Database session dependency injected by FastAPI
        
    Returns:
        dict: A response containing:
            - status (str): "success" if memories were generated successfully
            - memories_created (int): Number of memories that were created
            
    Raises:
        HTTPException: 
            - 404 if the user is not found
            - 500 if there's an error during memory generation or storage
    """
    try:
        result = await MemoryService.generate_user_memories(user_id, db)
        return {
            "status": "success",
            "memories_created": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing memories: {e}")

@router.get("/{user_id}")
async def get_user_memories(
    user_id: str,
    limit: int = 20,
    page: int = 1,
    category: Optional[str] = None
):
    """
    Retrieve paginated memories for a specific user with optional category filtering.
    
    Args:
        user_id (str): The ID of the user whose memories to retrieve
        limit (int): Maximum number of memories to return per page
        page (int): Page number for pagination
        category (Optional[str]): Filter memories by category
        
    Returns:
        dict: Status, user ID, and list of memories
        
    Raises:
        HTTPException: 500 if retrieval fails
    """
    try:
        memories = await MemoryService.get_memories(user_id, limit, category, page)

        return {
            "status": "success",
            "user_id": user_id,
            "memories": memories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch memories: {e}")

@router.delete("/{user_id}/delete-all")
async def delete_user_memories(user_id: str):
    """
    Delete all memories associated with a given user ID from Mem0.
    
    Args:
        user_id (str): The ID of the user whose memories should be deleted
        
    Returns:
        dict: Status, user ID, and deletion result
        
    Raises:
        HTTPException: 500 if deletion fails
    """
    logger.info(f"🗑️ Attempting to delete all memories for user {user_id}")
    try:
        result = await mem0_manager.client.delete_all(user_id=user_id)
        logger.info(f"✅ Deleted memories for user {user_id}")
        return {
            "status": "success",
            "user_id": user_id,
            "result": result
        }
    except Exception as e:
        logger.exception(f"❌ Failed to delete memories for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user memories: {e}")