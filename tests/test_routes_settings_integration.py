"""Integration tests for settings routes."""

from app.repositories.file_repository import Book


class TestBookSettingsRoutes:
    def test_settings_form_book_not_found(self, client):
        response = client.get("/books/99999/settings/")
        assert response.status_code == 404

    def test_settings_form_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={"temperature": 0.7, "top_p": 0.9, "max_tokens": 8192, "stream": False},
        ))
        response = client.get(f"/books/{book.id}/settings/")
        assert response.status_code == 200

    def test_save_settings_book_not_found(self, client):
        response = client.post("/books/99999/settings/")
        assert response.status_code == 404

    def test_save_settings_success(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={"temperature": 0.7, "top_p": 0.9, "max_tokens": 8192, "stream": False},
        ))
        response = client.post(
            f"/books/{book.id}/settings/",
            data={
                "temperature": "0.5",
                "top_p": "0.8",
                "max_tokens": "4096",
                "stream": "on",
                "jailbreak_prefix": "test_prefix",
                "system_template": "test_template",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_book(book.id)
        assert updated.config["temperature"] == 0.5
        assert updated.config["top_p"] == 0.8
        assert updated.config["max_tokens"] == 4096
        assert updated.config["stream"] is True

    def test_save_settings_with_prompts(self, client, repo):
        book = repo.create_book(Book(
            id=0, title="测试", genre="仙侠", target_chapters=3, basic_idea="创意",
            config={},
        ))
        response = client.post(
            f"/books/{book.id}/settings/",
            data={
                "prompt_chapter_writer_user_prompt": "custom_prompt",
                "temperature": "0.7",
                "top_p": "0.9",
                "max_tokens": "8192",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_book(book.id)
        assert updated.config["chapter_writer_user_prompt"] == "custom_prompt"


class TestGlobalSettingsRoutes:
    def test_global_settings_form(self, client):
        response = client.get("/settings/global")
        assert response.status_code == 200

    def test_save_global_settings(self, client, repo):
        response = client.post(
            "/settings/global",
            data={
                "deepseek_api_key": "test-key",
                "deepseek_base_url": "https://custom.api.com",
                "temperature": "0.5",
                "top_p": "0.8",
                "max_tokens": "4096",
                "prompt_jailbreak_prefix": "custom_jailbreak",
                "prompt_system_template": "custom_template",
                "agent_model_init_book": "custom-model",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        config = repo.get_global_config()
        assert config.deepseek_api_key == "test-key"
        assert config.deepseek_base_url == "https://custom.api.com"
        assert config.temperature == 0.5
        assert config.agent_models.get("init_book") == "custom-model"

    def test_save_global_settings_defaults(self, client, repo):
        response = client.post(
            "/settings/global",
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 303
        config = repo.get_global_config()
        assert config.deepseek_api_key == ""
        assert config.deepseek_base_url == "https://api.deepseek.com"
