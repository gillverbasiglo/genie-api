from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    groq_api_key: str
    database_url: str
    username: str
    password: str
    host: str 
    database: str

    model_config = SettingsConfigDict(env_file=".env")
