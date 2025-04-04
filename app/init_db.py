from .database import engine, Base
from .models.InvitationCode import InvitationCode
from .database import SessionLocal

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