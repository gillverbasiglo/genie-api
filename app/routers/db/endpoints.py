from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import AsyncSessionLocal

router = APIRouter(prefix="/debug", tags=["Debug"])

@router.get("/db-test")
async def db_test(db: AsyncSession = Depends(AsyncSessionLocal)):
    """
    Test if database connection is working.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        return {"ok": result.scalar() == 1}
    except Exception as e:
        return {"error": str(e)}
