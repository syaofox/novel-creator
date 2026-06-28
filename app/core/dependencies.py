import logging
from typing import Annotated

from fastapi import Depends

from app.config import settings as app_settings
from app.repositories.file_repository import FileRepository
from app.services.ai_service import AiService
from app.services.novel_service import NovelService
from app.utils.config_helper import get_global_config_dict

logger = logging.getLogger(__name__)

_repo: FileRepository | None = None


def get_repo() -> FileRepository:
    global _repo
    if _repo is None:
        _repo = FileRepository()
    return _repo


def get_ai_service(repo: FileRepository = Depends(get_repo)) -> AiService:
    global_config = get_global_config_dict(repo)
    api_key = global_config.get("deepseek_api_key") or app_settings.deepseek_api_key
    base_url = global_config.get("deepseek_base_url") or app_settings.deepseek_base_url
    model = global_config.get("default_model") or app_settings.default_model
    return AiService(
        api_key=api_key,
        base_url=base_url,
        model=model,
        global_config=global_config,
    )


def get_novel_service(
    repo: FileRepository = Depends(get_repo),
    ai_service: AiService = Depends(get_ai_service),
) -> NovelService:
    return NovelService(repo=repo, ai_service=ai_service)


RepoDep = Annotated[FileRepository, Depends(get_repo)]
AiServiceDep = Annotated[AiService, Depends(get_ai_service)]
NovelServiceDep = Annotated[NovelService, Depends(get_novel_service)]
