import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    default_model: str = os.getenv("DEFAULT_MODEL", "deepseek-chat")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/novel.db")


settings = Settings()
