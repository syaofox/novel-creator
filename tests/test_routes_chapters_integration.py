"""Integration tests for chapters routes."""

from app.main import app
from app.repositories.file_repository import Book


class TestChapterRoutes:
    def test_write_form_book_not_found(self, client):
        response = client.get("/books/99999/chapters/write")
        assert response.status_code == 404

    def test_write_form_default_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={"stream": False}, current_chapter=0,
        ))
        response = client.get(f"/books/{book.id}/chapters/write")
        assert response.status_code == 200

    def test_write_form_specific_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")
        response = client.get(f"/books/{book.id}/chapters/write?num=1")
        assert response.status_code == 200

    def test_write_form_invalid_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.get(f"/books/{book.id}/chapters/write?num=-1")
        assert response.status_code == 400

    def test_write_form_skip_chapter(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.get(f"/books/{book.id}/chapters/write?num=5")
        assert response.status_code == 400

    def test_read_chapter_not_found(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.get(f"/books/{book.id}/chapters/99")
        assert response.status_code == 404

    def test_read_chapter_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文内容", status="已完成")
        response = client.get(f"/books/{book.id}/chapters/1")
        assert response.status_code == 200
        assert "正文内容" in response.text

    def test_save_chapter_book_not_found(self, client):
        response = client.post("/books/99999/chapters/save", data={"chapter_number": 1, "content": "正文"})
        assert response.status_code == 404

    def test_save_chapter_invalid_number(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.post(f"/books/{book.id}/chapters/save", data={"chapter_number": 0, "content": "正文"})
        assert response.status_code == 400

    def test_save_chapter_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.post(f"/books/{book.id}/chapters/save", data={"chapter_number": 1, "content": "第一章正文"})
        assert response.status_code == 200
        chapter = repo.get_chapter(book.id, 1)
        assert chapter is not None
        assert chapter.status == "已完成"

    def test_delete_chapter_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")
        response = client.delete(f"/books/{book.id}/chapters/1")
        assert response.status_code == 200
        assert repo.get_chapter(book.id, 1) is None

    def test_delete_chapter_not_found(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.delete(f"/books/{book.id}/chapters/99")
        assert response.status_code == 404

    def test_delete_chapter_book_not_found(self, client):
        response = client.delete("/books/99999/chapters/1")
        assert response.status_code == 404

    def test_generate_chapter_book_not_found(self, client):
        response = client.post("/books/99999/chapters/", data={"core_event": "事件"})
        assert response.status_code == 404

    def test_chapter_list(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")
        response = client.get(f"/books/{book.id}/chapters/list")
        assert response.status_code == 200

    def test_chapter_list_book_not_found(self, client):
        response = client.get("/books/99999/chapters/list")
        assert response.status_code == 404

    def test_add_chapter_form(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.get(f"/books/{book.id}/chapters/add")
        assert response.status_code == 200

    def test_add_chapter_form_book_not_found(self, client):
        response = client.get("/books/99999/chapters/add")
        assert response.status_code == 404

    def test_add_chapter_endpoint_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.post(
            f"/books/{book.id}/chapters/add",
            data={"position": 1, "title": "新章节", "core_event": "新事件"},
        )
        assert response.status_code == 200
        chapter = repo.get_chapter(book.id, 1)
        assert chapter.title == "新章节"

    def test_add_chapter_book_not_found(self, client):
        response = client.post("/books/99999/chapters/add", data={"position": 1, "title": "新章节"})
        assert response.status_code == 404

    def test_regenerate_chapter_book_not_found(self, client):
        response = client.get("/books/99999/chapters/regenerate?num=1")
        assert response.status_code == 404

    def test_regenerate_chapter_invalid_num(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.get(f"/books/{book.id}/chapters/regenerate?num=0")
        assert response.status_code == 400

    def test_regenerate_chapter_not_created(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
        ))
        response = client.get(f"/books/{book.id}/chapters/regenerate?num=5")
        assert response.status_code == 400

    def test_optimize_outline_book_not_found(self, client):
        response = client.post(
            "/books/99999/chapters/optimize-outline",
            data={"position": 1, "title": "标题", "core_event": "事件"},
        )
        assert response.status_code == 404

    def test_generate_chapter_with_title(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={"stream": False}, current_chapter=0,
        ))
        from unittest.mock import AsyncMock, MagicMock
        from app.services.novel_service import NovelService
        mock_ai = MagicMock()
        mock_ai.global_config = {}
        mock_service = MagicMock(spec=NovelService)
        mock_service.get_book.return_value = book
        mock_service.get_prev_ending.return_value = ""
        mock_service.write_chapter = AsyncMock(return_value="章节内容")
        mock_service.get_chapters.return_value = []
        mock_service.ai_service = mock_ai
        from app.core.dependencies import get_novel_service
        app.dependency_overrides[get_novel_service] = lambda: mock_service
        try:
            response = client.post(
                f"/books/{book.id}/chapters/",
                data={"chapter_number": 1, "title": "自定义标题", "core_event": "核心事件"},
            )
            assert response.status_code == 200
            mock_service.write_chapter.assert_called_once_with(book, 1, "核心事件", "")
        finally:
            app.dependency_overrides.pop(get_novel_service, None)

    def test_save_chapter_with_title(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        response = client.post(
            f"/books/{book.id}/chapters/save",
            data={"chapter_number": 1, "title": "自定义标题", "content": "正文"},
        )
        assert response.status_code == 200
        chapter = repo.get_chapter(book.id, 1)
        assert chapter.title == "自定义标题"

    def test_regenerate_shows_form(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=1,
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", core_event="旧事件", status="已完成")
        response = client.get(f"/books/{book.id}/chapters/regenerate?num=1")
        assert response.status_code == 200
        assert "重新生成" in response.text

    def test_add_chapter_with_innerhtml_swap(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={}, current_chapter=0,
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文", status="已完成")
        response = client.post(
            f"/books/{book.id}/chapters/add",
            data={"position": 2, "title": "新章节", "core_event": "新事件"},
        )
        assert response.status_code == 200
        chapter = repo.get_chapter(book.id, 2)
        assert chapter.title == "新章节"

    def test_optimize_outline_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=5, basic_idea="创意",
            config={},
            style="语言简洁",
            memory_summary="【人物卡】\n张三\n【世界观】\n仙侠世界\n【风格规范】\n简洁",
        ))
        response = client.post(
            f"/books/{book.id}/chapters/optimize-outline",
            data={"position": 1, "title": "测试标题", "core_event": "测试事件"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "core_event" in data
