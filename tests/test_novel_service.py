"""Tests for NovelService, NovelRepository, and data layer."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Book, Chapter, GlobalConfig
from app.repositories.novel_repository import NovelRepository
from app.services.novel_service import NovelService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_book(db_session):
    book = Book(
        title="测试小说",
        genre="仙侠",
        target_chapters=5,
        basic_idea="一个测试创意",
        config={"temperature": 0.78, "top_p": 0.92, "max_tokens": 16384},
        memory_summary="【人物卡】\n张三: 主角\n【主线进度】\n第1章: 开始（已完成）\n【伏笔清单】\n- 无\n【其他信息】\n无",
        style="语言优美",
        current_chapter=0,
    )
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)
    return book


@pytest.fixture
def repo(db_session):
    return NovelRepository(db_session)


@pytest.fixture
def service(db_session):
    ai_service = MagicMock()
    ai_service.global_config = {}
    return NovelService(db_session, ai_service)


class TestNovelRepository:
    def test_create_book(self, repo, db_session):
        book = repo.create_book(
            title="新书",
            genre="玄幻",
            target_chapters=3,
            basic_idea="创意",
            config={},
        )
        assert book.id is not None
        assert book.title == "新书"
        assert book.current_chapter == 0

    def test_get_book_by_id(self, repo, sample_book):
        found = repo.get_book_by_id(sample_book.id)
        assert found is not None
        assert found.title == "测试小说"

    def test_get_book_by_id_not_found(self, repo):
        assert repo.get_book_by_id(999) is None

    def test_create_chapter(self, repo, sample_book):
        chapter = repo.create_chapter(
            book_id=sample_book.id,
            chapter_number=1,
            title="第1章",
            content="第一章内容",
            status="已完成",
        )
        assert chapter.id is not None
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
        repo.update_book(sample_book, title="新标题", current_chapter=3)
        updated = repo.get_book_by_id(sample_book.id)
        assert updated.title == "新标题"
        assert updated.current_chapter == 3

    def test_update_chapter(self, repo, sample_book):
        chapter = repo.create_chapter(sample_book.id, 1, "旧标题", "旧内容", status="未完成")
        repo.update_chapter(chapter, title="新标题", content="新内容", status="已完成")
        assert chapter.title == "新标题"
        assert chapter.content == "新内容"
        assert chapter.status == "已完成"

    def test_get_max_chapter_number(self, repo, sample_book):
        assert repo.get_max_chapter_number(sample_book.id) == 0
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.create_chapter(sample_book.id, 3, "第3章", "")
        assert repo.get_max_chapter_number(sample_book.id) == 3


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
        assert "第2章" in export
        assert "第二章内容" in export

    def test_add_chapter(self, service, sample_book):
        chapter = service.add_chapter(sample_book, 1, "新章节", "核心事件")
        assert chapter.chapter_number == 1

    def test_delete_chapter(self, service, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "内容1")
        repo.create_chapter(sample_book.id, 2, "第2章", "内容2")
        assert service.delete_chapter(sample_book, 1) is True
        remaining = service.get_chapter(sample_book.id, 1)
        assert remaining is not None
        assert remaining.content == "内容2"  # 旧第2章被重新编号为第1章
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
