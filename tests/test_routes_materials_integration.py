"""Integration tests for materials routes."""


class TestMaterialRoutes:
    def test_materials_page(self, client):
        response = client.get("/materials")
        assert response.status_code == 200
        assert "素材管理" in response.text

    def test_materials_page_with_tab(self, client):
        response = client.get("/materials?tab=style")
        assert response.status_code == 200

    def test_materials_partial(self, client):
        response = client.get("/materials/partial")
        assert response.status_code == 200

    def test_materials_partial_htmx(self, client):
        response = client.get("/materials/partial", headers={"HX-Request": "true"})
        assert response.status_code == 200


class TestPlotSummaryRoutes:
    def test_create_plot_summary(self, client, repo):
        response = client.post(
            "/materials/plot-summaries",
            data={"title": "测试剧情", "content": "剧情内容"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_plot_summary_with_source(self, client, repo):
        response = client.post(
            "/materials/plot-summaries",
            data={"title": "测试", "content": "内容", "source": "new_book"},
        )
        assert response.status_code == 200
        assert "select" in response.text.lower()

    def test_update_plot_summary(self, client, repo):
        item = repo.create_plot_summary(title="旧标题", content="旧内容")
        response = client.post(
            f"/materials/plot-summaries/{item.id}",
            data={"title": "新标题", "content": "新内容"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_plot_summary(item.id)
        assert updated.title == "新标题"

    def test_update_plot_summary_not_found(self, client):
        response = client.post("/materials/plot-summaries/99999", data={"title": "新标题", "content": ""})
        assert response.status_code == 404

    def test_delete_plot_summary(self, client, repo):
        item = repo.create_plot_summary(title="测试", content="内容")
        response = client.post(f"/materials/plot-summaries/{item.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_plot_summary(item.id) is None

    def test_delete_plot_summary_not_found(self, client):
        response = client.post("/materials/plot-summaries/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_edit_plot_summary_modal(self, client, repo):
        item = repo.create_plot_summary(title="测试", content="内容")
        response = client.get(f"/materials/plot-summaries/{item.id}/edit")
        assert response.status_code == 200

    def test_edit_plot_summary_modal_not_found(self, client):
        response = client.get("/materials/plot-summaries/99999/edit")
        assert response.status_code == 404


class TestCharacterCardRoutes:
    def test_create_character_card(self, client, repo):
        response = client.post(
            "/materials/character-cards",
            data={"title": "张三", "content": "主角"},
        )
        assert response.status_code == 200

    def test_create_character_card_with_source(self, client, repo):
        response = client.post(
            "/materials/character-cards",
            data={"title": "张三", "content": "主角", "source": "new_book"},
        )
        assert response.status_code == 200

    def test_create_character_card_auto_title(self, client, repo):
        response = client.post(
            "/materials/character-cards",
            data={"title": "", "content": "李四: 配角\n王五: 路人", "auto_title": "1"},
        )
        assert response.status_code == 200

    def test_update_character_card(self, client, repo):
        card = repo.create_character_card(title="旧名", content="旧内容")
        response = client.post(
            f"/materials/character-cards/{card.id}",
            data={"title": "新名", "content": "新内容", "confirm_overwrite": "1"},
        )
        assert response.status_code == 200
        updated = repo.get_character_card(card.id)
        assert updated.title == "新名"

    def test_update_character_card_not_found(self, client):
        response = client.post("/materials/character-cards/99999", data={"title": "新名", "content": ""})
        assert response.status_code == 404

    def test_delete_character_card(self, client, repo):
        card = repo.create_character_card(title="张三", content="内容")
        response = client.post(f"/materials/character-cards/{card.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_character_card(card.id) is None

    def test_delete_character_card_not_found(self, client):
        response = client.post("/materials/character-cards/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_edit_character_card_modal(self, client, repo):
        card = repo.create_character_card(title="张三", content="内容")
        response = client.get(f"/materials/character-cards/{card.id}/edit")
        assert response.status_code == 200

    def test_edit_character_card_modal_not_found(self, client):
        response = client.get("/materials/character-cards/99999/edit")
        assert response.status_code == 404

    def test_split_save_character_cards(self, client, repo):
        response = client.post(
            "/materials/character-cards/split-save",
            data={"content": "张三: 主角\n\n李四: 配角"}
        )
        assert response.status_code == 200


class TestWritingStyleRoutes:
    def test_create_writing_style(self, client, repo):
        response = client.post(
            "/materials/writing-styles",
            data={"title": "简洁风格", "content": "简洁"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_writing_style_with_default(self, client, repo):
        response = client.post(
            "/materials/writing-styles",
            data={"title": "默认风格", "content": "默认", "is_default": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        styles = repo.get_writing_styles()
        assert any(s.is_default == 1 for s in styles)

    def test_create_writing_style_with_source(self, client, repo):
        response = client.post(
            "/materials/writing-styles",
            data={"title": "测试", "content": "内容", "source": "new_book"},
        )
        assert response.status_code == 200

    def test_update_writing_style(self, client, repo):
        style = repo.create_writing_style(title="旧风格", content="旧内容")
        response = client.post(
            f"/materials/writing-styles/{style.id}",
            data={"title": "新风格", "content": "新内容"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_writing_style(style.id)
        assert updated.title == "新风格"

    def test_update_writing_style_not_found(self, client):
        response = client.post("/materials/writing-styles/99999", data={"title": "新风格", "content": ""})
        assert response.status_code == 404

    def test_delete_writing_style(self, client, repo):
        style = repo.create_writing_style(title="测试风格", content="内容")
        response = client.post(f"/materials/writing-styles/{style.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_writing_style(style.id) is None

    def test_delete_writing_style_not_found(self, client):
        response = client.post("/materials/writing-styles/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_delete_default_style_rejected(self, client, repo):
        style = repo.create_writing_style(title="默认", content="默认", is_default=1)
        response = client.post(f"/materials/writing-styles/{style.id}/delete")
        assert response.status_code == 400

    def test_edit_writing_style_modal(self, client, repo):
        style = repo.create_writing_style(title="测试", content="内容")
        response = client.get(f"/materials/writing-styles/{style.id}/edit")
        assert response.status_code == 200

    def test_edit_writing_style_modal_not_found(self, client):
        response = client.get("/materials/writing-styles/99999/edit")
        assert response.status_code == 404


class TestMaterialNoteRoutes:
    def test_create_material_note(self, client, repo):
        response = client.post(
            "/materials/material-notes",
            data={"title": "测试笔记", "content": "笔记内容"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_material_note_with_source(self, client, repo):
        response = client.post(
            "/materials/material-notes",
            data={"title": "测试", "content": "内容", "source": "new_book"},
        )
        assert response.status_code == 200

    def test_update_material_note(self, client, repo):
        note = repo.create_material_note(title="旧笔记", content="旧内容")
        response = client.post(
            f"/materials/material-notes/{note.id}",
            data={"title": "新笔记", "content": "新内容"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_material_note(note.id)
        assert updated.title == "新笔记"

    def test_update_material_note_not_found(self, client):
        response = client.post("/materials/material-notes/99999", data={"title": "新笔记", "content": ""})
        assert response.status_code == 404

    def test_delete_material_note(self, client, repo):
        note = repo.create_material_note(title="测试", content="内容")
        response = client.post(f"/materials/material-notes/{note.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_material_note(note.id) is None

    def test_delete_material_note_not_found(self, client):
        response = client.post("/materials/material-notes/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_edit_material_note_modal(self, client, repo):
        note = repo.create_material_note(title="测试", content="内容")
        response = client.get(f"/materials/material-notes/{note.id}/edit")
        assert response.status_code == 200

    def test_edit_material_note_modal_not_found(self, client):
        response = client.get("/materials/material-notes/99999/edit")
        assert response.status_code == 404


class TestBookInitDataRoutes:
    def test_create_book_init_data(self, client, repo):
        response = client.post(
            "/materials/book-init-data",
            data={"title": "模板", "content": "内容", "book_title": "书"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_update_book_init_data(self, client, repo):
        data = repo.create_book_init_data(title="旧模板", content="旧内容", book_title="旧书")
        response = client.post(
            f"/materials/book-init-data/{data.id}",
            data={"title": "新模板", "content": "新内容", "book_title": "新书"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        updated = repo.get_book_init_data(data.id)
        assert updated.title == "新模板"

    def test_update_book_init_data_not_found(self, client):
        response = client.post(
            "/materials/book-init-data/99999",
            data={"title": "新模板", "content": "", "book_title": ""},
        )
        assert response.status_code == 404

    def test_delete_book_init_data(self, client, repo):
        data = repo.create_book_init_data(title="模板", content="内容", book_title="书")
        response = client.post(f"/materials/book-init-data/{data.id}/delete", follow_redirects=False)
        assert response.status_code == 303
        assert repo.get_book_init_data(data.id) is None

    def test_delete_book_init_data_not_found(self, client):
        response = client.post("/materials/book-init-data/99999/delete", follow_redirects=False)
        assert response.status_code == 404

    def test_edit_book_init_data_modal(self, client, repo):
        data = repo.create_book_init_data(title="模板", content="内容", book_title="书")
        response = client.get(f"/materials/book-init-data/{data.id}/edit")
        assert response.status_code == 200

    def test_edit_book_init_data_modal_not_found(self, client):
        response = client.get("/materials/book-init-data/99999/edit")
        assert response.status_code == 404


class TestMaterialHelpers:
    def test_extract_character_names(self):
        from app.routes.materials import extract_character_names
        assert extract_character_names("张三: 主角") == ["张三"]
        assert extract_character_names("") == []
        assert extract_character_names("无冒号内容") == []
        assert extract_character_names("张三: 主角\n李四：配角") == ["张三", "李四"]

    def test_generate_character_card_title(self):
        from app.routes.materials import generate_character_card_title
        assert generate_character_card_title("") == "未命名人物卡"
        assert generate_character_card_title("张三: 主角") == "张三"
        assert generate_character_card_title("张三: 主角\n李四：配角") in ["张三、李四", "张三"]

    def test_split_characters(self):
        from app.routes.materials import split_characters
        result = split_characters("张三: 主角\n  - 武功高强\n\n李四：配角\n  - 胆小")
        assert len(result) >= 2
        assert result[0]["name"] == "张三"
