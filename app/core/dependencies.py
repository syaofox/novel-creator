import logging
from functools import lru_cache
from typing import Annotated
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import SessionLocal
from app.services.ai_service import AiService
from app.services.novel_service import NovelService
from app.utils.config_helper import get_global_config_dict

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def _get_global_config() -> dict:
    return {}


def get_ai_service(db: Session = Depends(get_db)) -> AiService:
    global_config = get_global_config_dict(db)
    return AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=global_config.get("default_model") or app_settings.default_model,
        global_config=global_config,
    )


def get_novel_service(db: Session = Depends(get_db), ai_service: AiService = Depends(get_ai_service)) -> NovelService:
    return NovelService(db=db, ai_service=ai_service)


AiServiceDep = Annotated[AiService, Depends(get_ai_service)]
NovelServiceDep = Annotated[NovelService, Depends(get_novel_service)]
DbSession = Annotated[Session, Depends(get_db)]
