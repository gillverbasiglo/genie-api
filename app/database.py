from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from .config import settings

# PostgreSQL connection string
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{settings.db_username}:{settings.db_password.get_secret_value()}@{settings.host}:{settings.port}/{settings.database}"

# Create an async engine
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Create an async sessionmaker
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # ensures that after commit, objects won't be expired
)

Base = declarative_base()
