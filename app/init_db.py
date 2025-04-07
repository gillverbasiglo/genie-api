from sqlalchemy import create_engine
from .database import engine, Base
from sqlalchemy.orm import sessionmaker
from .database import SessionLocal
from .config import settings
from .models.User import User
from .models.Invitation import Invitation

# PostgreSQL connection string
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.db_username}:{settings.db_password}@{settings.host}:{settings.port}/{settings.database}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import all models here
    from .models.User import Base
    from .models.Invitation import Base
    
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
