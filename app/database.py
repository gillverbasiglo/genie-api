from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# PostgreSQL connection string
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{settings.db_username}:{settings.db_password.get_secret_value()}@{settings.host}:{settings.port}/{settings.database}"

print("🚀 database.py loaded")
# Log the connection string (mask password for safety)
masked_url = SQLALCHEMY_DATABASE_URL.replace(
    settings.db_password.get_secret_value(), "*****"
)
logger.info(f"🔧 SQLAlchemy DB URL: {masked_url}")

# Create an async engine
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL
    )

AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

Base = declarative_base()