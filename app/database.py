from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# PostgreSQL connection string
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.db_username}:{settings.db_password.get_secret_value()}@{settings.host}:{settings.port}/{settings.database}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
