from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    groq_api_key: str
    database_url: str = "postgresql+asyncpg://username:password@localhost/genie_db"

    model_config = SettingsConfigDict(env_file=".env")