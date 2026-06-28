"""Integration tests for FastAPI routes.

Uses a file-based temp SQLite database to avoid in-memory isolation issues.
All POST requests that create resources use follow_redirects=False to check
for 303 redirect responses.
"""

import atexit
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import Book, Chapter, GlobalConfig

_tmp_fd, _tmp_path = tempfile.mkstemp(suffix=".db")


def _cleanup():
    os.close(_tmp_fd)
    try:
        os.unlink(_tmp_path)
    except OSError:
        pass


atexit.register(_cleanup)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_tmp_path}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


class TestHomePage:
    def test_home_page(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_home_page_with_status(self, client):
        response = client.get("/?status=已完结")
        assert response.status_code == 200

    def test_home_page_htmx(self, client):
        response = client.get("/", headers={"HX-Request": "true"})
        assert response.status_code == 200


class TestBooksRoutes:
    def test_new_book_form(self, client):
        response = client.get("/books/new")
        assert response.status_code == 200
        assert "新建小说" in response.text

    def test_create_book(self, client):
        response = client.post(
            "/books/",
            data={
                "title": "测试小说",
                "genre": "仙侠",
                "target_chapters": 3,
                "characters": "[]",
                "world_view": "{}",
                "outline": '[{"chapter": 1, "title": "第1章", "core_event": "开始"}]',
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_and_view_book(self, client):
        response = client.post(
            "/books/",
            data={
                "title": "测试小说",
                "genre": "仙侠",
                "target_chapters": 3,
                "characters": "[]",
                "world_view": "{}",
                "outline": '[{"chapter": 1, "title": "第1章", "core_event": "开始"}]',
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        book_id = int(response.headers["location"].split("/")[-1])

        response = client.get(f"/books/{book_id}")
        assert response.status_code == 200
        assert "创作区" in response.text

    def test_view_nonexistent_book(self, client):
        response = client.get("/books/99999")
        assert response.status_code == 404

    def _create_book(self, client, title="测试小说"):
        response = client.post(
            "/books/",
            data={"title": title, "genre": "仙侠", "target_chapters": 3},
            follow_redirects=False,
        )
        assert response.status_code == 303
        return int(response.headers["location"].split("/")[-1])

    def test_finish_book(self, client):
        book_id = self._create_book(client)

        response = client.post(f"/books/{book_id}/finish", follow_redirects=False)
        assert response.status_code == 303

    def test_delete_book(self, client):
        book_id = self._create_book(client)

        response = client.post(f"/books/{book_id}/delete", follow_redirects=False)
        assert response.status_code == 303

        response = client.get(f"/books/{book_id}")
        assert response.status_code == 404


class TestChapterRoutes:
    def test_write_chapter_form(self, client):
        book_id = self._create_book(client)

        response = client.get(f"/books/{book_id}/chapters/write")
        assert response.status_code == 200
        assert "写第" in response.text

    def test_chapter_list_html(self, client):
        response = client.post(
            "/books/",
            data={
                "title": "测试小说",
                "genre": "仙侠",
                "target_chapters": 3,
                "characters": "[]",
                "world_view": "{}",
                "outline": (
                    '[{"chapter": 1, "title": "第1章", "core_event": "开始"},'
                    '{"chapter": 2, "title": "第2章", "core_event": "发展"},'
                    '{"chapter": 3, "title": "第3章", "core_event": "结局"}]'
                ),
            },
            follow_redirects=False,
        )
        book_id = int(response.headers["location"].split("/")[-1])

        response = client.get(f"/books/{book_id}")
        assert response.status_code == 200
        assert "第1章" in response.text

    def test_save_chapter(self, client):
        book_id = self._create_book(client)

        response = client.post(
            f"/books/{book_id}/chapters/save",
            data={"chapter_number": 1, "content": "第一章正文内容"},
        )
        assert response.status_code == 200
        assert "成功" in response.text

    def test_read_chapter(self, client):
        book_id = self._create_book(client)

        client.post(
            f"/books/{book_id}/chapters/save",
            data={"chapter_number": 1, "content": "第一章正文内容"},
        )

        response = client.get(f"/books/{book_id}/chapters/1")
        assert response.status_code == 200
        assert "第一章正文内容" in response.text

    def test_read_nonexistent_chapter(self, client):
        book_id = self._create_book(client)

        response = client.get(f"/books/{book_id}/chapters/99")
        assert response.status_code == 404

    def test_add_chapter(self, client):
        book_id = self._create_book(client)

        response = client.post(
            f"/books/{book_id}/chapters/add",
            data={"position": 1, "title": "新章节", "core_event": "新事件"},
        )
        assert response.status_code == 200

    def test_delete_chapter(self, client):
        book_id = self._create_book(client)

        client.post(
            f"/books/{book_id}/chapters/save",
            data={"chapter_number": 1, "content": "第一章内容"},
        )

        response = client.delete(f"/books/{book_id}/chapters/1")
        assert response.status_code == 200

    def _create_book(self, client, title="测试小说"):
        response = client.post(
            "/books/",
            data={"title": title, "genre": "仙侠", "target_chapters": 5},
            follow_redirects=False,
        )
        assert response.status_code == 303
        return int(response.headers["location"].split("/")[-1])


class TestSettingsRoutes:
    def test_global_settings(self, client):
        response = client.get("/settings/global")
        assert response.status_code == 200

    def test_book_settings(self, client):
        response = client.post(
            "/books/",
            data={"title": "测试小说", "genre": "仙侠", "target_chapters": 3},
            follow_redirects=False,
        )
        book_id = int(response.headers["location"].split("/")[-1])

        response = client.get(f"/books/{book_id}/settings/")
        assert response.status_code == 200


class TestMaterialRoutes:
    def test_materials_page(self, client):
        response = client.get("/materials")
        assert response.status_code == 200
        assert "素材管理" in response.text


class TestExportRoute:
    def test_export_book(self, client):
        response = client.post(
            "/books/",
            data={"title": "测试小说", "genre": "仙侠", "target_chapters": 3},
            follow_redirects=False,
        )
        book_id = int(response.headers["location"].split("/")[-1])

        client.post(
            f"/books/{book_id}/chapters/save",
            data={"chapter_number": 1, "content": "第一章正文"},
        )

        response = client.get(f"/books/{book_id}/export")
        assert response.status_code == 200
        assert "测试小说" in response.text
