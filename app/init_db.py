from sqlalchemy import create_engine
from .database import engine, Base
from sqlalchemy.orm import sessionmaker
from .database import SessionLocal
from .config import settings

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
