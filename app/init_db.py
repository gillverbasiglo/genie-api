from sqlalchemy import create_engine
from .database import engine, Base
from sqlalchemy.orm import sessionmaker
from .database import SessionLocal
from .config import settings
from .models.User import User
from .models.invitation import Invitation

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    
    # Create all tables
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Creating database tables...")
    init_db()
    print("Database tables created successfully!") 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
