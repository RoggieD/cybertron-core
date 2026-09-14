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
    kokoro_base_url: str = "http://localhost:8880/v1"
    kokoro_container_name: str = "kokoro-fastapi"
    kokoro_container_port: int = 8880
    kokoro_model: str = "kokoro"
    kokoro_voice: str = "af_heart"
    whisper_base_url: str = "http://127.0.0.1:9001/v1"
    whisper_api_key: str = ""
    whisper_model: str = "whisper-1"
    whisper_language: str = "en"
    whisper_prompt: str = (
        "CyberTron C.O.R.E., GM-AI01, Kokoro, Whisper, Ollama, Qwen, "
        "Qwen3.5, Langfuse, Open WebUI, NVIDIA, RTX 3060, Zabbix, "
        "Paperless-ngx, Docker, FastAPI, Firefox, Linux."
    )
    database_url: str = "sqlite:///./data/cybertron.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CYBERTRON_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
