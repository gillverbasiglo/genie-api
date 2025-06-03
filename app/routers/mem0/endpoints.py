# app/routers/mem0/endpoints.py

import logging
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
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


# Configure logging for this module
logger = logging.getLogger(__name__)

# Initialize router with prefix and tags for API documentation
router = APIRouter(prefix="/memories", tags=["memories"])

mem0_manager = Mem0Manager()

@router.post("/{user_id}/rebuild")
async def rebuild_memories(user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await MemoryService.create_user_memories(user_id, db)
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
    try:
        memories = await MemoryService.get_memories(user_id, limit, category, page)

        return {
            "status": "success",
            "user_id": user_id,
            "memories": memories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch memories: {e}")


@router.post("/{user_id}/add")
async def add_memory_for_user(user_id: str, payload: dict):
    """
    Add a single memory for a user under a specific category.
    Allowed categories: private_chat, user_archetypes, user_keywords
    """
    logger.info(f"🧠 Adding memory for user {user_id} | payload: {payload}")
    result = None
    try:

        result = await mem0_manager.client.add(
            messages=[{
                "role": "user",
                "content": payload["content"]
            }],
            user_id=user_id,
            metadata=build_metadata(payload["category"]),
            infer=False,
            output_format="v1.1"
        )

        logger.info(f"✅ Memory added successfully for user {user_id}")

    except Exception as e:
        content = None
        if hasattr(e, 'response') and e.response is not None:
            try:
                content = await e.response.aread()
                logger.error(f"❌ Mem0 response content for '{payload['category']}': {content.decode('utf-8')}")
            except Exception as read_error:
                logger.error(f"❌ Failed to read error response content: {read_error}")
        logger.exception(f"❌ Exception adding memory for user {user_id}: {e}")

    return {
        "status": "success",
        "mem0_result": result
    }
