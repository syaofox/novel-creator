"""Integration tests for books routes."""

from app.repositories.file_repository import Book


class TestBooksRoutes:
    def test_preview_book(self, client):
        response = client.post(
            "/books/preview",
            data={
                "title": "测试小说",
                "genre": "仙侠",
                "target_chapters": 3,
                "basic_idea": "一个创意",
            },
        )
        assert response.status_code == 200
        assert "测试小说" in response.text

    def test_preview_with_init_data_json(self, client):
        response = client.post(
            "/books/preview",
            data={
                "title": "测试",
                "target_chapters": 3,
                "init_data": '{"characters": [{"name": "张三"}], "outline": [{"chapter": 1, "title": "第1章"}]}',
            },
        )
        assert response.status_code == 200
        assert "第1章" in response.text

    def test_preview_with_init_data_markers(self, client):
        response = client.post(
            "/books/preview",
            data={
                "title": "测试",
                "target_chapters": 3,
                "init_data": "【characters】[{\"name\": \"张三\"}]【characters】",
            },
        )
        assert response.status_code == 200

    def test_create_book_success(self, client, repo):
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
        book = repo.get_book(book_id)
        assert book is not None
        assert book.title == "测试小说"
        assert book.genre == "仙侠"

    def test_create_book_htmx(self, client, repo):
        response = client.post(
            "/books/",
            data={
                "title": "测试小说",
                "genre": "仙侠",
                "target_chapters": 3,
                "characters": "[]",
                "world_view": "{}",
                "outline": '[{"chapter": 1, "title": "第1章"}]',
            },
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "创作区" in response.text

    def test_create_book_with_all_fields(self, client, repo):
        response = client.post(
            "/books/",
            data={
                "title": "测试小说",
                "genre": "玄幻",
                "target_chapters": 5,
                "plot_summary": "剧情梗概",
                "character_card": "人物卡内容",
                "notes": "注意事项",
                "temperature": "0.8",
                "top_p": "0.95",
                "max_tokens": "8192",
                "stream": "true",
                "style": "语言优美",
                "characters": '[{"name": "主角"}]',
                "world_view": '{"setting": "玄幻世界"}',
                "outline": '[{"chapter": 1, "title": "第1章"}]',
                "foreshadowing": '["伏笔1"]',
                "other": '{"novel_title": "测试小说"}',
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_book_detail_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
        ))
        response = client.get(f"/books/{book.id}")
        assert response.status_code == 200
        assert "创作区" in response.text

    def test_book_detail_not_found(self, client):
        response = client.get("/books/99999")
        assert response.status_code == 404

    def test_delete_book_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
        ))
        response = client.post(f"/books/{book.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_book(book.id) is None

    def test_delete_book_not_found(self, client):
        response = client.post("/books/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_finish_book_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
        ))
        response = client.post(f"/books/{book.id}/finish", follow_redirects=False)
        assert response.status_code == 303
        updated = repo.get_book(book.id)
        assert updated.status == "已完结"

    def test_finish_book_not_found(self, client):
        response = client.post("/books/99999/finish", follow_redirects=False)
        assert response.status_code == 404

    def test_unfinish_book(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            status="已完结",
        ))
        response = client.post(f"/books/{book.id}/unfinish")
        assert response.status_code == 200
        updated = repo.get_book(book.id)
        assert updated.status == "进行中"

    def test_export_book(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
        ))
        repo.create_chapter(book.id, 1, "第1章", "正文内容", status="已完成")
        response = client.get(f"/books/{book.id}/export")
        assert response.status_code == 200
        assert "测试" in response.text
        assert "正文内容" in response.text

    def test_export_book_not_found(self, client):
        response = client.get("/books/99999/export")
        assert response.status_code == 404

    def test_new_book_form(self, client):
        response = client.get("/books/new")
        assert response.status_code == 200
        assert "新建小说" in response.text
