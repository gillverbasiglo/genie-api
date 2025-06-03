import logging
import os
from datetime import datetime, timezone
import uuid
from mem0 import AsyncMemoryClient
from typing import List, Optional
from app.config import settings
from app.core.mem0.mem0_helpers import build_metadata


# Configure logger for this module
logger = logging.getLogger(__name__)


class Mem0Manager:
    def __init__(self):
        self.client = AsyncMemoryClient(api_key=settings.MEM0_API_KEY.get_secret_value())

    async def store_private_message(
        self,
        user_id: str,
        receiver_id: str,
        content: str,
        category: str
    ):
        
        metadata = build_metadata(category, {"receiver_id": str(receiver_id)})
    
        try:
            result = await self.client.add(
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                user_id=user_id,
                metadata=metadata
            )
            return result
        except Exception as e:
            logger.exception(f"Error adding memory to Mem0: {e}")
            return None
        
    async def store_user_archetypes_bulk(self, user_id: str, archetypes: list, category: str):
        success_count = 0
        
        logger.info(f"🧠 Storing {len(archetypes)} archetypes for user '{user_id}' under category '{category}'")
        
        for arch in archetypes:
            message = [{
                "role": "user",
                "content": arch["name"]
            }]
            metadata = build_metadata(category)

            logger.debug(f"→ Archetype: {arch['name']} | Metadata: {metadata}")
            
            try:
                result = await self.client.add(
                    messages=message,
                    user_id=user_id,
                    metadata=metadata,
                    infer=False,
                    output_format="v1.1"
                )
                logger.debug(f"✅ Mem0 response for '{arch['name']}': {result}")
                success_count += 1
            except Exception as e:
                content = None
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        content = await e.response.aread()
                        logger.error(f"❌ Mem0 response content for '{arch['name']}': {content.decode('utf-8')}")
                    except Exception as read_error:
                        logger.error(f"❌ Failed to read error response content: {read_error}")
                logger.exception(f"❌ Exception adding archetype '{arch['name']}': {e}")

        logger.info(f"✅ Finished storing archetypes: {success_count}/{len(archetypes)} added successfully")
        return {"added": success_count, "total": len(archetypes)}
    
    async def store_user_keywords_bulk(self, user_id: str, keywords: list, category: str):
        success_count = 0
        messages = []
        metadata = build_metadata(category)

        logger.info(f"🧠 Storing {len(keywords)} keywords for user '{user_id}' under category '{category}'")
        
        for keyword in keywords:
            message = {
                "role": "user",
                "content": keyword["name"]
            }
            messages.append(message)
        
        logger.info(f"Sending messages: {messages}")
        try:
            await self.client.add(
                messages=messages,
                user_id=user_id,
                metadata=metadata,
                infer=False,
                output_format="v1.1"
            )
            logger.info(f"✅ Added {len(messages)} keywords to Mem0")
            success_count = len(messages)
        except Exception as e:
            logger.exception(f"Failed to add archetype memories in bulk: {e}")
    
        return {"added": success_count, "total": len(keywords)}

    async def get_recent_memories(
        self,
        user_id: str,
        limit: int,
        category: str,
        page: int
    ):
        logger.info(f"🔍 Getting recent memories for user '{user_id}' in category '{category}'")
        try:
            memories = []
            if (category): 
                filters = {
                    "AND":[
                        {"user_id":user_id},
                        {"metadata": {"category": category}}
                    ]
                } 
                memories = await self.client.get_all(version="v2", filters=filters, page=page, page_size=limit)
            else:
                memories = await self.client.get_all(user_id=user_id, page=page, page_size=limit)
            logger.info(f"Memories: {memories}")
            return memories
        except Exception as e:
            logger.exception(f"❌ Error getting memories: {e}")
            return []

mem0_manager = Mem0Manager()
