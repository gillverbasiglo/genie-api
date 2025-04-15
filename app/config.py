from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .secrets_manager import SecretsManager

class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    environment: str = "development"
    host: str
    db_username: str
    db_password: SecretStr
    database: str
    port: int = 5432
    groq_api_key: SecretStr  
    openai_api_key: SecretStr  
    trip_advisor_api_key: SecretStr  
    google_api_key: SecretStr
    tavily_api_key: SecretStr
    exa_api_key: SecretStr
    aviation_stack_api_key: SecretStr
    tmdb_api_key: SecretStr
    push_notification_url: SecretStr
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("db_username", "db_password", "groq_api_key", "openai_api_key", "trip_advisor_api_key", "google_api_key", "tavily_api_key", "exa_api_key", "aviation_stack_api_key", "tmdb_api_key",  "push_notification_url", mode="before")
    @classmethod
    def load_secrets(cls, v, info):
        if info.data.get("environment") == "production":
            try:
                secrets = SecretsManager(region_name=info.data.get("aws_region"))
                if info.field_name == "groq_api_key":
                    v = secrets.get_api_key("groq")
                elif info.field_name == "openai_api_key":
                    v = secrets.get_api_key("openai")
                elif info.field_name == "trip_advisor_api_key":
                    v = secrets.get_api_key("trip-advisor")
                elif info.field_name == "google_api_key":
                    v = secrets.get_api_key("google")
                elif info.field_name == "tavily_api_key":
                    v = secrets.get_api_key("tavily")
                elif info.field_name == "exa_api_key":
                    v = secrets.get_api_key("exa")
                elif info.field_name == "aviation_stack_api_key":
                    v = secrets.get_api_key("aviation-stack")
                elif info.field_name == "tmdb_api_key":
                    v = secrets.get_api_key("tmdb")
                elif info.field_name == "db_username":
                    v = secrets.get_db_credentials()['username']
                elif info.field_name == "db_password":
                    v = secrets.get_db_credentials()['password']
                elif info.field_name == "push_notification_url":
                    v = secrets.get_db_credentials()['push_notification_url']
                return v
            except Exception as e:
                # If there's an error getting secrets, fall back to the env value
                return v
        return v

settings = Settings()
