import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.mem0.mem0_manager import mem0_manager
from app.models.chat.private_chat_message import Message
from app.models.user import User

# Configure logging for this module
logger = logging.getLogger(__name__)


class MemoryService:
    @staticmethod
    async def create_user_memories(user_id: str, db: AsyncSession) -> dict:
        result = {"archetypes": 0, "keywords": 0, "messages": 0}

        logger.info(f"🧠 [Mem0] Starting memory generation for user: {user_id}")

        try:
            user_row = await db.execute(select(User).where(User.id == user_id))
            user = user_row.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            # Decode archetypes safely
            try:
                archetypes = json.loads(user.archetypes) if isinstance(user.archetypes, str) else user.archetypes or []
                logger.debug(f"🔍 Parsed archetypes: {archetypes}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse archetypes for user {user_id}: {e}")
                archetypes = []

            if archetypes:
                try:
                    response  = await mem0_manager.store_user_archetypes_bulk(
                        user_id=str(user.id),
                        archetypes=archetypes,
                        category="user_archetypes"
                    )
                    logger.info(f"✅ Archetypes stored: {response}")
                    result["archetypes"] = len(archetypes)
                except Exception as e:
                    logger.exception(f"❌ Error storing archetypes in bulk: {e}")
            else:
                logger.info(f"ℹ️ No archetypes to store for user {user_id}")

            # Decode keywords safely
            try:
                keywords = json.loads(user.keywords) if isinstance(user.keywords, str) else user.keywords or []
                logger.debug(f"🔍 Parsed keywords: {keywords}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse archetypes for user {user_id}: {e}")
                archetypes = []
            
            if keywords:
                try:
                    response = await mem0_manager.store_user_keywords_bulk(
                        user_id=str(user.id),
                        keywords=keywords,
                        category="user_keywords"
                    )
                    logger.info(f"✅ Keywords stored: {response}")
                    result["keywords"] = len(keywords)
                except Exception as e:
                    logger.exception(f"❌ Error storing keywords in bulk: {e}")
            else:
                logger.info(f"ℹ️ No keywords to store for user {user_id}")

            logger.info(f"🎉 Memory creation complete for user {user_id}: {result}")
            return result

        except Exception as e:
            logger.exception(f"🔥 Unhandled error in create_user_memories for user {user_id}: {e}")
            raise

    @staticmethod
    async def get_memories(user_id: str, limit: int, category: str, page: int) -> dict:
        try:
            memories = await mem0_manager.get_recent_memories(
                user_id=user_id,
                limit=limit,
                category=category,
                page=page
            )
            return memories
        except Exception as e:
            logger.exception(f"❌ Error getting memories: {e}")
            raise
