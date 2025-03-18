from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import Settings
from .secrets_manager import SecretsManager

# PostgreSQL connection string
settings = Settings()
secrets = SecretsManager(region_name=settings.aws_region)
db_credentials = secrets.get_db_credentials()
SQLALCHEMY_DATABASE_URL = f"postgresql://{db_credentials['username']}:{db_credentials['password']}@{settings.host}:{settings.port}/{settings.database}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
