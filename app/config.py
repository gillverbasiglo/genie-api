from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    host: str
    database: str
    port: int = 5432
    model_config = SettingsConfigDict(env_file=".env")
