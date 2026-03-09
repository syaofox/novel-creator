import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    default_model: str = os.getenv("DEFAULT_MODEL", "deepseek-chat")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./novel.db")

    class Config:
        env_file = ".env"

settings = Settings()