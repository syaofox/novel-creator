"""Tests for NovelService and FileRepository using temporary file storage."""

import os
import tempfile

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.repositories.file_repository import FileRepository, Book, Chapter
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
        config={"temperature": 0.78, "top_p": 0.92, "max_tokens": 16384},
        memory_summary="【人物卡】\n张三: 主角\n【主线进度】\n第1章: 开始（已完成）\n【伏笔清单】\n- 无\n【其他信息】\n无",
        style="语言优美",
        current_chapter=0,
    ))
    return book


@pytest.fixture
def service(repo):
    ai_service = MagicMock()
    ai_service.global_config = {}
    return NovelService(repo=repo, ai_service=ai_service)


class TestFileRepository:
    def test_create_book(self, repo):
        book = repo.create_book(Book(id=0, title="新书", genre="玄幻", target_chapters=3, basic_idea="创意"))
        assert book.id > 0
        assert book.title == "新书"
        assert book.current_chapter == 0
        assert book.created_at

    def test_get_book(self, repo, sample_book):
        found = repo.get_book(sample_book.id)
        assert found is not None
        assert found.title == "测试小说"

    def test_get_book_not_found(self, repo):
        assert repo.get_book(999) is None

    def test_get_books_by_status(self, repo, sample_book):
        books = repo.get_books(status="进行中")
        assert any(b.id == sample_book.id for b in books)

    def test_get_books_empty_status(self, repo, sample_book):
        books = repo.get_books(status="已完结")
        assert not any(b.id == sample_book.id for b in books)

    def test_create_chapter(self, repo, sample_book):
        chapter = repo.create_chapter(sample_book.id, 1, "第1章", "第一章内容", status="已完成")
        assert chapter.chapter_number == 1
        assert chapter.content == "第一章内容"

    def test_get_chapter(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 1, "第1章", "内容")
        chapter = repo.get_chapter(sample_book.id, 1)
        assert chapter is not None
        assert chapter.title == "第1章"

    def test_get_chapters_ordered(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 2, "第2章", "内容2")
        repo.create_chapter(sample_book.id, 1, "第1章", "内容1")
        chapters = repo.get_chapters(sample_book.id)
        assert len(chapters) == 2
        assert chapters[0].chapter_number == 1
        assert chapters[1].chapter_number == 2

    def test_get_prev_ending(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 1, "第1章", "这是第一章的结尾内容。")
        ending = repo.get_prev_ending(sample_book.id, 2, chars=600)
        assert "结尾内容" in ending

    def test_get_prev_ending_first_chapter(self, repo, sample_book):
        ending = repo.get_prev_ending(sample_book.id, 1)
        assert ending == ""

    def test_get_prev_ending_no_prev(self, repo, sample_book):
        ending = repo.get_prev_ending(sample_book.id, 2)
        assert ending == ""

    def test_update_book(self, repo, sample_book):
        sample_book.title = "新标题"
        sample_book.current_chapter = 3
        repo.update_book(sample_book)
        updated = repo.get_book(sample_book.id)
        assert updated.title == "新标题"
        assert updated.current_chapter == 3

    def test_update_chapter(self, repo, sample_book):
        chapter = repo.create_chapter(sample_book.id, 1, "旧标题", "旧内容", status="未完成")
        repo.update_chapter(chapter, title="新标题", content="新内容", status="已完成")
        updated = repo.get_chapter(sample_book.id, 1)
        assert updated.title == "新标题"
        assert updated.content == "新内容"
        assert updated.status == "已完成"

    def test_get_max_chapter_number(self, repo, sample_book):
        assert repo.get_max_chapter_number(sample_book.id) == 0
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.create_chapter(sample_book.id, 3, "第3章", "")
        assert repo.get_max_chapter_number(sample_book.id) == 3

    def test_delete_book(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.delete_book(sample_book.id)
        assert repo.get_book(sample_book.id) is None

    def test_renumber_chapters(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 1, "第1章", "内容1")
        repo.create_chapter(sample_book.id, 2, "第2章", "内容2")
        repo.renumber_chapters(sample_book.id, 1, offset=1)
        ch2 = repo.get_chapter(sample_book.id, 2)
        assert ch2 is not None

    def test_insert_chapter_at(self, repo, sample_book):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.create_chapter(sample_book.id, 2, "第2章", "")
        repo.insert_chapter_at(sample_book.id, 2, "新章节", "事件")
        assert repo.get_chapter(sample_book.id, 2).title == "新章节"
        assert repo.get_chapter(sample_book.id, 3).title == "第2章"


class TestGlobalConfig:
    def test_get_global_config_defaults(self, repo):
        config = repo.get_global_config()
        assert config.id == 1
        assert config.temperature == 0.78

    def test_save_global_config(self, repo):
        config = repo.get_global_config()
        config.deepseek_api_key = "test-key"
        config.temperature = 0.5
        repo.save_global_config(config)
        loaded = repo.get_global_config()
        assert loaded.deepseek_api_key == "test-key"
        assert loaded.temperature == 0.5


class TestMaterials:
    def test_plot_summary_crud(self, repo):
        created = repo.create_plot_summary(title="测试剧情", content="内容")
        assert created.id > 0
        items = repo.get_plot_summaries()
        assert any(i.id == created.id for i in items)

        repo.update_plot_summary(created.id, title="新标题")
        updated = repo.get_plot_summary(created.id)
        assert updated.title == "新标题"

        assert repo.delete_plot_summary(created.id) is True
        assert repo.get_plot_summary(created.id) is None

    def test_character_card_crud(self, repo):
        card = repo.create_character_card(title="张三", content="主角")
        assert card.id > 0
        assert repo.get_character_card(card.id).title == "张三"
        repo.delete_character_card(card.id)
        assert repo.get_character_card(card.id) is None

    def test_writing_style_crud(self, repo):
        style = repo.create_writing_style(title="简洁", content="简洁风格", is_default=1)
        assert style.is_default == 1
        styles = repo.get_writing_styles()
        assert any(s.id == style.id for s in styles)

    def test_material_note_crud(self, repo):
        note = repo.create_material_note(title="笔记", content="内容")
        assert note.id > 0
        repo.update_material_note(note.id, title="新笔记")
        assert repo.get_material_note(note.id).title == "新笔记"

    def test_book_init_data_crud(self, repo):
        data = repo.create_book_init_data(title="模板1", content="内容", book_title="书")
        assert data.id > 0
        items = repo.get_book_init_data_list()
        assert any(i.id == data.id for i in items)


class TestNovelService:
    def test_get_book(self, service, sample_book):
        book = service.get_book(sample_book.id)
        assert book.title == "测试小说"

    def test_get_chapters(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.create_chapter(sample_book.id, 2, "第2章", "")
        chapters = service.get_chapters(sample_book.id)
        assert len(chapters) == 2

    def test_save_chapter_new(self, service, sample_book):
        chapter, is_new = service.save_chapter(sample_book, 1, "第一章内容", "第1章")
        assert is_new is True
        assert chapter.chapter_number == 1
        assert chapter.content == "第一章内容"
        assert chapter.status == "已完成"
        updated_book = service.get_book(sample_book.id)
        assert updated_book.current_chapter == 1

    def test_save_chapter_update_existing(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "旧内容")
        chapter, is_new = service.save_chapter(sample_book, 1, "新内容")
        assert is_new is False
        assert chapter.content == "新内容"

    def test_finish_book(self, service, sample_book):
        service.finish_book(sample_book)
        assert sample_book.status == "已完结"

    def test_delete_book(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        service.delete_book(sample_book)
        assert service.get_book(sample_book.id) is None

    @pytest.mark.asyncio
    async def test_update_summary_missing_chapter(self, service, sample_book):
        with pytest.raises(ValueError, match="章节不存在"):
            await service.update_summary(sample_book, 1)

    def test_get_book_export(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "第一章内容。")
        repo.create_chapter(sample_book.id, 2, "第2章", "第二章内容。")
        export = service.get_book_export_content(sample_book)
        assert "测试小说" in export
        assert "第1章" in export
        assert "第一章内容" in export

    def test_add_chapter(self, service, sample_book):
        chapter = service.add_chapter(sample_book, 1, "新章节", "核心事件")
        assert chapter.chapter_number == 1

    def test_delete_chapter(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "内容1")
        repo.create_chapter(sample_book.id, 2, "第2章", "内容2")
        assert service.delete_chapter(sample_book, 1) is True
        remaining = service.get_chapter(sample_book.id, 1)
        assert remaining is not None
        assert remaining.content == "内容2"
        assert len(service.get_chapters(sample_book.id)) == 1

    def test_delete_chapter_not_found(self, service, sample_book):
        assert service.delete_chapter(sample_book, 99) is False

    def test_extract_title_from_markdown(self, service, sample_book):
        title = service._extract_title("# 第一章标题\n正文内容")
        assert title == "第一章标题"

    def test_extract_title_from_first_line(self, service, sample_book):
        title = service._extract_title("这是一个足够长的第一章标题内容")
        assert title is not None

    def test_extract_title_empty(self, service, sample_book):
        title = service._extract_title("")
        assert title is None
