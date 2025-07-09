import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.init_db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["Debug"])

@router.get("/db-test")
async def db_test(db: AsyncSession = Depends(get_db)):
    """
    Test if database connection is working.
    """
    try:
        logger.info("Testing database connection")
        result = await db.execute(text("SELECT 1"))
        return {"ok": result.scalar() == 1}
    except Exception as e:
        return {"error": str(e)}
