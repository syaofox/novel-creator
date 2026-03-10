import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_STYLE,
    DEFAULT_MODEL,
)

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    default_model: str = os.getenv("DEFAULT_MODEL", DEFAULT_MODEL)
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/novel.db")

    default_temperature: float = float(os.getenv("DEFAULT_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
    default_top_p: float = float(os.getenv("DEFAULT_TOP_P", str(DEFAULT_TOP_P)))
    default_max_tokens: int = int(os.getenv("DEFAULT_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    default_stream: bool = os.getenv("DEFAULT_STREAM", str(DEFAULT_STREAM)).lower() == "true"
    default_jailbreak_prefix: str = os.getenv("DEFAULT_JAILBREAK_PREFIX", DEFAULT_JAILBREAK_PREFIX)
    default_system_template: str = os.getenv("DEFAULT_SYSTEM_TEMPLATE", DEFAULT_SYSTEM_TEMPLATE)
    default_style: str = os.getenv("DEFAULT_STYLE", DEFAULT_STYLE)


settings = Settings()
