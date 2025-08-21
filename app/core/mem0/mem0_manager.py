import logging
from datetime import datetime, timezone
from mem0 import AsyncMemoryClient
from typing import Optional
from app.config import settings
from app.core.mem0.mem0_helpers import build_metadata


# Configure logger for this module
logger = logging.getLogger(__name__)


class Mem0Manager:
    """
    Manager class for interacting with the Mem0 memory service.
    
    This class provides methods for storing and retrieving various types of user data
    including private messages, archetypes, and keywords. It handles the communication
    with the Mem0 API and manages error handling and logging.
    """
    
    def __init__(self):
        """Initialize the Mem0Manager with API credentials from settings."""
        self.client = AsyncMemoryClient(api_key=settings.mem0_api_key.get_secret_value())

    async def store_private_message(
        self,
        user_id: str,
        receiver_id: str,
        content: str,
        category: str
    ) -> Optional[dict]:
        """
        Store a private message in Mem0.

        Args:
            user_id (str): The ID of the user sending the message
            receiver_id (str): The ID of the message recipient
            content (str): The message content to store
            category (str): The category to store the message under

        Returns:
            Optional[dict]: The result from Mem0 if successful, None if failed
        """
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
        """
        Store multiple user archetypes in Mem0 in bulk.

        This method processes a list of archetypes and stores each one in Mem0 with associated metadata.
        Each archetype is stored with its name and similarity score in the metadata.

        Args:
            user_id (str): The unique identifier of the user
            archetypes (list): List of dictionaries containing archetype data. Each dictionary should have:
                - name (str): The name of the archetype
                - similarity_score (float): The similarity score for the archetype
            category (str): The category under which to store the archetypes

        Returns:
            dict: A dictionary containing:
                - added (int): Number of successfully added archetypes
                - total (int): Total number of archetypes attempted to add

        Note:
            The method logs detailed information about the process, including success and failure
            of individual archetype additions. Failed additions are logged but don't stop the process.
        """
        success_count = 0
        
        logger.info(f"🧠 Storing {len(archetypes)} archetypes for user '{user_id}' under category '{category}'")
        
        for arch in archetypes:
            message = [{
                "role": "user",
                "content": arch["name"]
            }]
            extra = {
                "name": arch["name"],
                "similarity_score": arch["similarity_score"]
            }
            metadata = build_metadata(category, extra)
            logger.info(f"→ Archetype: {arch['name']} | Metadata: {metadata}")
            
            try:
                result = await self.client.add(
                    messages=message,
                    user_id=user_id,
                    metadata=metadata,
                    infer=True,
                    output_format="v1.1"
                )
                logger.info(f"✅ Mem0 response for '{arch['name']}': {result}")
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
        """
        Store multiple user keywords in Mem0 in bulk.

        This method processes a list of keywords and stores each one in Mem0 with associated metadata.
        Each keyword is stored with its name and similarity score in the metadata.

        Args:
            user_id (str): The unique identifier of the user
            keywords (list): List of dictionaries containing keyword data. Each dictionary should have:
                - name (str): The name of the keyword
                - similarity_score (float): The similarity score for the keyword
            category (str): The category under which to store the keywords

        Returns:
            dict: A dictionary containing:
                - added (int): Number of successfully added keywords
                - total (int): Total number of keywords attempted to add

        Note:
            The method logs detailed information about the process, including success and failure
            of individual keyword additions. Failed additions are logged but don't stop the process.
            Each keyword is stored with inference enabled and uses the v1.1 output format.
        """
        success_count = 0
        
        logger.info(f"🧠 Storing {len(keywords)} keywords for user '{user_id}' under category '{category}'")
        
        for keyword in keywords:
            message = [{
                "role": "user",
                "content": keyword["name"]
            }]
            extra = {
                "name": keyword["name"],
                "similarity_score": keyword["similarity_score"]
            }
            metadata = build_metadata(category, extra)
            logger.info(f"→ Keyword: {keyword['name']} | Metadata: {metadata}")
            
            try:
                result = await self.client.add(
                    messages=message,
                    user_id=user_id,
                    metadata=metadata,
                    infer=True,
                    output_format="v1.1"
                )
                logger.info(f"✅ Mem0 response for '{keyword['name']}': {result}")
                success_count += 1
            except Exception as e:
                content = None
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        content = await e.response.aread()
                        logger.error(f"❌ Mem0 response content for '{keyword['name']}': {content.decode('utf-8')}")
                    except Exception as read_error:
                        logger.error(f"❌ Failed to read error response content: {read_error}")
                logger.exception(f"❌ Exception adding keyword '{keyword['name']}': {e}")

        logger.info(f"✅ Finished storing keywords: {success_count}/{len(keywords)} added successfully")
        return {"added": success_count, "total": len(keywords)}
    

    async def get_recent_memories(
        self,
        user_id: str,
        limit: int,
        category: str,
        page: int
    ) -> list:
        """
        Retrieve recent memories for a user from Mem0.

        Args:
            user_id (str): The ID of the user
            limit (int): Maximum number of memories to retrieve
            category (str): Optional category to filter memories by
            page (int): Page number for pagination

        Returns:
            list: List of memories retrieved from Mem0
        """
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
        
    async def store_user_interaction(
        self,
        user_id: str,
        query: str,
        location_data: dict = None,
        model_used: str = None,
        session_id: str = None,
        additional_metadata: dict = None
    ) -> Optional[dict]:
        try:
            content_parts = []
            content_parts.append(f"User Query: {query}")
            content = "\n\n".join(content_parts)

            metadata = {
                "category": "user_interactions",
                "query": query[:100],
                "model_used": model_used,
                "location_data": location_data,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": additional_metadata or {}
            }

            result = await self.client.add(
                messages=[{"role": "user", "content": content}],
                user_id=user_id,
                metadata=metadata
            )

            logger.info(f"Successfully stored user interaction for user '{user_id}'")
            logger.info(f"Mem0 Result: {result}")

            return result

        except Exception as e:
            logger.exception(f"Error storing user interaction for user '{user_id}': {e}")
            return None
    

# Create a singleton instance of Mem0Manager
mem0_manager = Mem0Manager()
