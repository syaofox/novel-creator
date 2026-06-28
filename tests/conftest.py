import os
import tempfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_repo, get_ai_service, get_novel_service
from app.repositories.file_repository import FileRepository, Book
from app.services.novel_service import NovelService


@pytest.fixture
def repo():
    tmpdir = tempfile.mkdtemp()
    book_dir = os.path.join(tmpdir, "books")
    data_dir = os.path.join(tmpdir, "data")
    os.makedirs(book_dir)
    os.makedirs(data_dir)
    yield FileRepository(data_dir=data_dir, books_dir=book_dir)


@pytest.fixture
def sample_book(repo):
    book = repo.create_book(Book(
        id=0,
        title="测试小说",
        genre="仙侠",
        target_chapters=5,
        basic_idea="一个测试创意",
        config={"temperature": 0.78, "top_p": 0.92, "max_tokens": 16384, "stream": False},
        memory_summary="【人物卡】\n张三: 主角\n【主线进度】\n第1章: 开始（已完成）\n【伏笔清单】\n- 无\n【其他信息】\n无",
        style="语言优美",
        current_chapter=0,
    ))
    return book


@pytest.fixture
def mock_ai_service():
    ai_service = MagicMock()
    ai_service.global_config = {}
    return ai_service


@pytest.fixture
def service(repo, mock_ai_service):
    return NovelService(repo=repo, ai_service=mock_ai_service)


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repo] = lambda: repo

    mock_ai = MagicMock()
    mock_ai.global_config = {}
    app.dependency_overrides[get_ai_service] = lambda: mock_ai

    from app.services.novel_service import NovelService
    test_service = NovelService(repo=repo, ai_service=mock_ai)
    app.dependency_overrides[get_novel_service] = lambda: test_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_repo, None)
    app.dependency_overrides.pop(get_ai_service, None)
    app.dependency_overrides.pop(get_novel_service, None)
