"""Tests for character card duplicate name check."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_repo
from app.repositories.file_repository import FileRepository


@pytest.fixture
def client():
    tmpdir = tempfile.mkdtemp()
    book_dir = os.path.join(tmpdir, "books")
    data_dir = os.path.join(tmpdir, "data")
    os.makedirs(book_dir)
    os.makedirs(data_dir)
    test_repo = FileRepository(data_dir=data_dir, books_dir=book_dir)

    app.dependency_overrides[get_repo] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_repo, None)


class TestCharacterCardDuplicateName:
    def _create_card(self, client, title: str, content: str = ""):
        return client.post(
            "/materials/character-cards", data={"title": title, "content": content}, follow_redirects=False
        )

    def test_create_unique_name_saves(self, client):
        """Creating a card with a unique name should succeed and redirect."""
        resp = self._create_card(client, "张三", "主角")
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/materials?tab=character"

    def test_create_duplicate_name_returns_warning(self, client):
        """Creating a card with a duplicate name should return a warning."""
        self._create_card(client, "张三", "主角设定")
        resp = self._create_card(client, "张三", "另一个设定")
        assert resp.status_code == 200
        assert "同名人物卡" in resp.text
        assert "张三" in resp.text
        assert "覆盖保存" in resp.text
        assert "主角设定" in resp.text

    def test_create_duplicate_with_confirm_saves(self, client):
        """Creating a card with a duplicate name and confirm_overwrite should save."""
        self._create_card(client, "张三", "主角设定")
        resp = client.post(
            "/materials/character-cards",
            data={"title": "张三", "content": "另一个设定", "confirm_overwrite": "1"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/materials?tab=character"

    def test_create_multiple_duplicates_allowed(self, client):
        """User can create multiple cards with the same name by confirming."""
        self._create_card(client, "张三", "第一版")
        client.post(
            "/materials/character-cards",
            data={"title": "张三", "content": "第二版", "confirm_overwrite": "1"},
            follow_redirects=False,
        )
        resp = client.get("/materials?tab=character")
        assert resp.status_code == 200
        assert resp.text.count("张三") >= 2

    def test_update_to_duplicate_name_returns_warning(self, client):
        """Updating a card to a name that matches another card should warn."""
        self._create_card(client, "张三", "主角")
        self._create_card(client, "李四", "配角")
        resp = client.post(
            "/materials/character-cards/2", data={"title": "张三", "content": "配角变主角"}, follow_redirects=False
        )
        assert resp.status_code == 200
        assert "同名人物卡" in resp.text
        assert "覆盖保存" in resp.text

    def test_update_to_duplicate_with_confirm_saves(self, client):
        """Updating with confirm_overwrite=1 should save despite duplicate."""
        self._create_card(client, "张三", "主角")
        self._create_card(client, "李四", "配角")
        resp = client.post(
            "/materials/character-cards/2",
            data={"title": "张三", "content": "配角变主角", "confirm_overwrite": "1"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/materials?tab=character"

    def test_update_same_name_no_warning(self, client):
        """Updating a card with its own name should not trigger a warning."""
        self._create_card(client, "张三", "主角")
        resp = client.post(
            "/materials/character-cards/1", data={"title": "张三", "content": "更新后的设定"}, follow_redirects=False
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/materials?tab=character"

    def test_split_save_duplicate_returns_warning(self, client):
        """Split-save with duplicate names should return warning HTML instead of saving."""
        self._create_card(client, "张三")
        content = "张三: 主角\n性格：勇敢\n\n李四: 配角\n性格：温柔"
        resp = client.post("/materials/character-cards/split-save", data={"content": content})
        assert resp.status_code == 200
        assert "发现同名人物" in resp.text
        assert "张三" in resp.text
        assert "覆盖保存" in resp.text
        assert "X-New-Ids" not in resp.headers

    def test_split_save_duplicate_with_confirm_saves(self, client):
        """Split-save with duplicate names and confirm_overwrite should save."""
        self._create_card(client, "张三")
        content = "张三: 主角\n性格：勇敢\n\n李四: 配角\n性格：温柔"
        resp = client.post(
            "/materials/character-cards/split-save",
            data={"content": content, "confirm_overwrite": "1"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-New-Ids") is not None
        assert resp.headers.get("X-Duplicate-Names") is not None

    def test_split_save_no_duplicate(self, client):
        """Split-save without duplicates should save and not include X-Duplicate-Names header."""
        content = "张三: 主角\n性格：勇敢\n\n李四: 配角\n性格：温柔"
        resp = client.post("/materials/character-cards/split-save", data={"content": content})
        assert resp.status_code == 200
        assert resp.headers.get("X-New-Ids") is not None
        assert resp.headers.get("X-Duplicate-Names") is None

    def test_create_auto_title_duplicate_check(self, client):
        """Auto-generated title should also be checked for duplicates."""
        self._create_card(client, "张三", "张三: 主角")
        resp = self._create_card(client, "", "张三: 另一个主角")
        assert resp.status_code == 200
        assert "同名人物卡" in resp.text

    def test_update_nonexistent_card(self, client):
        """Updating a non-existent card should return 404."""
        resp = client.post(
            "/materials/character-cards/99999", data={"title": "测试", "content": "内容"}, follow_redirects=False
        )
        assert resp.status_code == 404

    def test_warning_content_truncated(self, client):
        """The warning should show truncated content of the existing card."""
        long_content = "A" * 200
        self._create_card(client, "张三", long_content)
        resp = self._create_card(client, "张三", "新内容")
        assert "A" * 80 in resp.text
        assert "..." in resp.text
