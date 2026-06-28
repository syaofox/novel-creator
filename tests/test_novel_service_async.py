"""Tests for NovelService async methods."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.repositories.file_repository import Book
from app.services.novel_service import NovelService


class TestNovelServiceAsync:
    @pytest.fixture
    def service_with_mock(self, repo):
        ai_service = MagicMock()
        ai_service.global_config = {}
        return NovelService(repo=repo, ai_service=ai_service)

    @pytest.mark.asyncio
    async def test_update_summary_with_content(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "第一章正文内容", status="已完成")
        sample_book.current_chapter = 1

        agent_mock = MagicMock()
        agent_mock.update = AsyncMock(return_value="新摘要")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.SummaryAgent",
                lambda *args, **kwargs: agent_mock,
            )
            result = await service_with_mock.update_summary(sample_book, 1)
            assert result == "新摘要"
            agent_mock.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_summary_with_core_event_only(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "", core_event="核心事件")
        sample_book.current_chapter = 1

        agent_mock = MagicMock()
        agent_mock.update = AsyncMock(return_value="摘要")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.SummaryAgent",
                lambda *args, **kwargs: agent_mock,
            )
            result = await service_with_mock.update_summary(sample_book, 1)
            assert result == "摘要"

    @pytest.mark.asyncio
    async def test_update_summary_empty_chapter_raises(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "", core_event="")
        sample_book.current_chapter = 1

        with pytest.raises(ValueError, match="章节内容和核心事件都为空"):
            await service_with_mock.update_summary(sample_book, 1)

    @pytest.mark.asyncio
    async def test_update_summary_no_chapter_number(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "正文", status="已完成")
        sample_book.current_chapter = 1

        agent_mock = MagicMock()
        agent_mock.update = AsyncMock(return_value="摘要")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.SummaryAgent",
                lambda *args, **kwargs: agent_mock,
            )
            result = await service_with_mock.update_summary(sample_book)
            assert result == "摘要"

    @pytest.mark.asyncio
    async def test_stream_update_summary(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "正文", status="已完成")
        sample_book.current_chapter = 1

        async def async_gen():
            yield "chunk1"
            yield "chunk2"

        agent_mock = MagicMock()
        agent_mock.update_stream = MagicMock(return_value=async_gen())

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.SummaryAgent",
                lambda *args, **kwargs: agent_mock,
            )
            chunks = []
            async for chunk in service_with_mock.stream_update_summary(sample_book, 1):
                chunks.append(chunk)
            assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_stream_update_summary_missing_chapter(self, service_with_mock, sample_book):
        with pytest.raises(ValueError, match="章节不存在"):
            async for _ in service_with_mock.stream_update_summary(sample_book, 99):
                pass

    @pytest.mark.asyncio
    async def test_stream_update_summary_empty_content(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "", core_event="")
        sample_book.current_chapter = 1

        with pytest.raises(ValueError, match="章节内容和核心事件都为空"):
            async for _ in service_with_mock.stream_update_summary(sample_book, 1):
                pass

    @pytest.mark.asyncio
    async def test_write_chapter(self, service_with_mock, sample_book):
        agent_mock = MagicMock()
        agent_mock.write = AsyncMock(return_value="章节内容")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.ChapterWriterAgent",
                lambda *args, **kwargs: agent_mock,
            )
            result = await service_with_mock.write_chapter(sample_book, 1, "事件", "前情")
            assert result == "章节内容"
            agent_mock.write.assert_called_once_with(1, "事件", "前情")

    @pytest.mark.asyncio
    async def test_stream_write_chapter(self, service_with_mock, sample_book):
        async def async_gen():
            yield "chunk1"

        agent_mock = MagicMock()
        agent_mock.write_stream = MagicMock(return_value=async_gen())

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.novel_service.ChapterWriterAgent",
                lambda *args, **kwargs: agent_mock,
            )
            chunks = []
            async for chunk in service_with_mock.stream_write_chapter(sample_book, 1, "事件", "前情"):
                chunks.append(chunk)
            assert chunks == ["chunk1"]

    def test_update_chapter_title_and_core_event(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "旧标题", "", core_event="旧事件")
        service_with_mock.update_chapter_title_and_core_event(sample_book, 1, "新标题", "新事件")
        chapter = repo.get_chapter(sample_book.id, 1)
        assert chapter.title == "新标题"
        assert chapter.core_event == "新事件"

    def test_update_chapter_title_only(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "旧标题", "")
        service_with_mock.update_chapter_title_and_core_event(sample_book, 1, "新标题", "")
        chapter = repo.get_chapter(sample_book.id, 1)
        assert chapter.title == "新标题"

    def test_update_chapter_nonexistent(self, service_with_mock, sample_book):
        service_with_mock.update_chapter_title_and_core_event(sample_book, 99, "标题", "事件")

    def test_save_chapter_new_without_title(self, service_with_mock, sample_book):
        chapter, is_new = service_with_mock.save_chapter(sample_book, 1, "正文内容")
        assert is_new is True
        assert chapter.title is not None

    def test_save_chapter_with_title(self, service_with_mock, sample_book):
        chapter, is_new = service_with_mock.save_chapter(sample_book, 1, "正文", "自定义标题")
        assert chapter.title == "自定义标题"

    def test_save_chapter_updates_current_chapter(self, service_with_mock, sample_book):
        service_with_mock.save_chapter(sample_book, 3, "正文")
        updated = service_with_mock.get_book(sample_book.id)
        assert updated.current_chapter == 3

    def test_get_max_chapter_number(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        repo.create_chapter(sample_book.id, 5, "第5章", "")
        assert service_with_mock.get_max_chapter_number(sample_book.id) == 5

    def test_get_prev_ending(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "结尾内容")
        ending = service_with_mock.get_prev_ending(sample_book.id, 2)
        assert "结尾内容" in ending

    def test_add_chapter_too_small_position(self, service_with_mock, sample_book):
        chapter = service_with_mock.add_chapter(sample_book, 0, "新章节")
        assert chapter.chapter_number == 1

    def test_add_chapter_too_large_position(self, service_with_mock, sample_book, repo):
        repo.create_chapter(sample_book.id, 1, "第1章", "")
        chapter = service_with_mock.add_chapter(sample_book, 10, "新章节")
        assert chapter.chapter_number == 2

    def test_add_chapter_updates_target(self, service_with_mock, sample_book):
        service_with_mock.add_chapter(sample_book, 1, "新章节")
        updated = service_with_mock.get_book(sample_book.id)
        assert updated.target_chapters >= 1

    @pytest.mark.asyncio
    async def test_optimize_outline_calls_llm(self, service_with_mock, sample_book):
        service_with_mock.ai_service.call_llm = AsyncMock(
            return_value='{"title": "优化标题", "core_event": "优化事件"}'
        )
        result = await service_with_mock.optimize_outline(sample_book, 1, "原标题", "原事件")
        assert result["title"] == "优化标题"
        assert result["core_event"] == "优化事件"
        service_with_mock.ai_service.call_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_outline_fallback_on_invalid_json(self, service_with_mock, sample_book):
        service_with_mock.ai_service.call_llm = AsyncMock(return_value="非JSON内容")
        result = await service_with_mock.optimize_outline(sample_book, 1, "原标题", "原事件")
        assert result["title"] == "原标题"
        assert result["core_event"] == "原事件"
