"""Integration tests for AI routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.dependencies import get_repo, get_ai_service, get_novel_service
from app.repositories.file_repository import Book


class TestAIRoutes:
    def test_update_summary_book_not_found(self, client):
        response = client.post("/books/99999/ai/update-summary")
        assert response.status_code == 404

    def test_stream_summary_book_not_found(self, client, repo):
        response = client.post("/books/99999/ai/stream-summary")
        assert response.status_code == 404

    def test_save_summary_book_not_found(self, client):
        response = client.post("/books/99999/ai/save-summary", data={"summary": "test"})
        assert response.status_code == 404

    def test_save_summary_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试小说", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")
        book.current_chapter = 1
        repo.update_book(book)

        response = client.post(
            f"/books/{book.id}/ai/save-summary",
            data={"summary": "新摘要"},
        )
        assert response.status_code == 200
        assert "保存成功" in response.text

    def test_save_summary_with_chapter_updates(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="玄幻", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")

        response = client.post(
            f"/books/{book.id}/ai/save-summary",
            data={"summary": "摘要", "title": "新标题", "core_event": "新事件", "chapter": 1},
        )
        assert response.status_code == 200

        chapter = repo.get_chapter(book.id, 1)
        assert chapter.title == "新标题"
        assert chapter.core_event == "新事件"

    def test_save_summary_updates_current_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="玄幻", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=2,
        ))
        repo.create_chapter(book.id, 2, "第2章", "正文", status="已完成")

        response = client.post(
            f"/books/{book.id}/ai/save-summary",
            data={"summary": "摘要", "core_event": "事件"},
        )
        assert response.status_code == 200

        chapter = repo.get_chapter(book.id, 2)
        assert chapter.core_event == "事件"

    def test_update_style_book_not_found(self, client):
        response = client.post("/books/99999/ai/update-style")
        assert response.status_code == 404

    def test_update_style_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="玄幻", target_chapters=3, basic_idea="创意",
            config={}, style="旧风格",
        ))
        response = client.post(
            f"/books/{book.id}/ai/update-style",
            data={"style": "新风格"},
        )
        assert response.status_code == 200
        updated = repo.get_book(book.id)
        assert updated.style == "新风格"
