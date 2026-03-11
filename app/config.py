from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    deepseek_api_key: str = Field(default="")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1")
    default_model: str = Field(default=DEFAULT_MODEL)
    database_url: str = Field(default="sqlite:///./data/novel.db")

    default_temperature: float = Field(default=DEFAULT_TEMPERATURE)
    default_top_p: float = Field(default=DEFAULT_TOP_P)
    default_max_tokens: int = Field(default=DEFAULT_MAX_TOKENS)
    default_stream: bool = Field(default=DEFAULT_STREAM)
    default_jailbreak_prefix: str = Field(default=DEFAULT_JAILBREAK_PREFIX)
    default_system_template: str = Field(default=DEFAULT_SYSTEM_TEMPLATE)
    default_style: str = Field(default=DEFAULT_STYLE)


settings = Settings()
