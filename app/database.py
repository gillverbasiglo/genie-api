from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings

# PostgreSQL connection string
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{settings.db_username}:{settings.db_password.get_secret_value()}@{settings.host}:{settings.port}/{settings.database}"

# Create an async engine
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10,          # more than default (default is 5)
    max_overflow=20,      # allow some overflow
    pool_timeout=30,      # wait 30s before giving up
    echo=False,           # can be True for debugging
    future=True
    )

AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

Base = declarative_base()