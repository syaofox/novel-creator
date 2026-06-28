"""Integration tests for chapters routes."""

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
