"""Edge case tests for uncovered code paths."""

import pytest
from app.repositories.file_repository import Book


class TestAIErrorPaths:
    def test_update_summary_no_current_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.post(f"/books/{book.id}/ai/update-summary")
        assert response.status_code == 400

    def test_update_summary_current_chapter_not_exist(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        response = client.post(f"/books/{book.id}/ai/update-summary")
        assert response.status_code == 400
        assert "不存在" in response.text

    def test_update_summary_empty_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        repo.create_chapter(book.id, 1, "第1章", "", core_event="")
        response = client.post(f"/books/{book.id}/ai/update-summary")
        assert response.status_code == 400
        assert "为空" in response.text

    def test_stream_summary_no_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.post(f"/books/{book.id}/ai/stream-summary")
        assert response.status_code == 400

    def test_save_summary_updates_core_event_only(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="玄幻", target_chapters=3, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        repo.create_chapter(book.id, 1, "旧标题", "正文", core_event="旧事件")
        response = client.post(
            f"/books/{book.id}/ai/save-summary",
            data={"summary": "摘要", "core_event": "新事件"},
        )
        assert response.status_code == 200
        chapter = repo.get_chapter(book.id, 1)
        assert chapter.core_event == "新事件"
        assert chapter.title == "旧标题"


class TestGenerateChapterEndpoints:
    def test_generate_chapter_skip(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={"stream": False}, current_chapter=0,
        ))
        response = client.post(
            f"/books/{book.id}/chapters/",
            data={"chapter_number": 5, "core_event": "事件"},
        )
        assert response.status_code == 400
        assert "跳章" in response.text

    def test_generate_chapter_stream_mode(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={"stream": True}, current_chapter=0,
        ))
        response = client.post(
            f"/books/{book.id}/chapters/",
            data={"core_event": "事件"},
        )
        assert response.status_code == 200

    def test_stream_chapter_skip(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={"stream": True}, current_chapter=0,
        ))
        response = client.post(
            f"/books/{book.id}/chapters/stream",
            data={"chapter_number": 5, "core_event": "事件"},
        )
        assert response.status_code == 400
        assert "跳章" in response.text

    def test_save_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.post(
            f"/books/{book.id}/chapters/save",
            data={"chapter_number": 1, "content": "正文"},
        )
        assert response.status_code == 200


class TestExceptions:
    def test_exceptions_importable(self):
        from app.core.exceptions import (
            NovelCreatorException,
            BookNotFoundError,
            ChapterNotFoundError,
            AIServiceError,
            ValidationError,
        )
        assert issubclass(BookNotFoundError, NovelCreatorException)
        assert issubclass(ChapterNotFoundError, NovelCreatorException)
        assert issubclass(AIServiceError, NovelCreatorException)
        assert issubclass(ValidationError, NovelCreatorException)

        err = BookNotFoundError(1)
        assert err.status_code == 404
        assert "1" in err.message

        err2 = ChapterNotFoundError(1, 5)
        assert err2.status_code == 404
        assert "第5章" in err2.message
        assert err2.details == {"book_id": 1, "chapter": 5}

        err3 = AIServiceError("服务故障")
        assert err3.status_code == 503

        err4 = ValidationError("无效输入")
        assert err4.status_code == 400


class TestChapterOutlineExtraction:
    def test_extract_chapter_outline(self):
        from app.routes.chapters import extract_chapter_outline
        assert extract_chapter_outline("", 1) == ""

        summary = "【主线进度】\n第1章: 开始\n第2章: 发展"
        result = extract_chapter_outline(summary, 1)
        assert result == "开始"

        result = extract_chapter_outline(summary, 3)
        assert result == ""

    def test_extract_chapter_outline_no_marker(self):
        from app.routes.chapters import extract_chapter_outline
        assert extract_chapter_outline("无标记内容", 1) == ""

    def test_extract_chapter_outline_no_match(self):
        from app.routes.chapters import extract_chapter_outline
        summary = "【主线进度】\n一些内容"
        result = extract_chapter_outline(summary, 5)
        assert result == ""


class TestPreviewBook:
    def test_preview_with_init_data_markers(self, client, repo):
        response = client.post(
            "/books/preview",
            data={
                "title": "测试",
                "target_chapters": 3,
                "init_data": "【characters】[{\"name\": \"张三\"}]【characters】\n【other】{\"novel_title\": \"测试\"}【other】",
            },
        )
        assert response.status_code == 200
        assert "张三" in response.text

    def test_preview_with_invalid_json_init_data(self, client, repo):
        response = client.post(
            "/books/preview",
            data={
                "title": "测试",
                "target_chapters": 3,
                "init_data": '{"invalid": json}',
            },
        )
        assert response.status_code == 200


class TestWritingStyleExtract:
    def test_extract_style_not_found(self, client):
        style = client.post("/materials/writing-styles/99999/delete")
        assert style.status_code == 404
