from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    open_ai_api_key: str
    google_api_key: str

    model_config = SettingsConfigDict(env_file=".env")
    