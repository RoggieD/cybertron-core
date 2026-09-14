from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CyberTron C.O.R.E."
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    ollama_base_url: str = "http://localhost:11434"
    ollama_num_predict: int = 4096
    ollama_num_ctx: int = 32768
    database_url: str = "sqlite:///./data/cybertron.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CYBERTRON_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
