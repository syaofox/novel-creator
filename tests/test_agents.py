"""Tests for AI agents - InitBookAgent, SummaryAgent, StyleExtractorAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.agents import InitBookAgent, SummaryAgent, StyleExtractorAgent
from app.services.agents.base_agent import AgentFactory
from app.constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS


def _make_book(**kwargs):
    book = MagicMock()
    for k, v in {"config": {}, "style": "", "memory_summary": ""}.items():
        setattr(book, k, kwargs.pop(k, v))
    for k, v in kwargs.items():
        setattr(book, k, v)
    return book


class TestInitBookAgent:
    @pytest.fixture
    def agent(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        return InitBookAgent(ai_service, global_config={})

    def test_build_prompt(self, agent):
        prompt = agent.build_prompt("test idea", "仙侠", 10)
        assert "test idea" in prompt
        assert "仙侠" in prompt
        assert "10" in prompt

    def test_with_style_adds_section(self, agent):
        agent.with_style("语言简洁")
        prompt_text = agent._get_role_prompt()
        assert "语言简洁" in prompt_text

    @pytest.mark.asyncio
    async def test_initialize_parses_response(self, agent):
        agent.ai_service.call_with_messages = AsyncMock(
            return_value='{"characters": [{"name": "张三"}], "world_view": {}, "style": {}, "outline": [], "foreshadowing": [], "other": {}}'
        )
        result = await agent.initialize("test", "仙侠", 5)
        assert result["characters"] is not None
        assert "张三" in str(result["characters"])

    @pytest.mark.asyncio
    async def test_initialize_empty_response(self, agent):
        agent.ai_service.call_with_messages = AsyncMock(return_value="")
        result = await agent.initialize("test", "仙侠", 5)
        assert result["characters"] == ""
        assert result["outline"] == ""

    def test_factory_can_create(self):
        instance = AgentFactory.create("init_book", MagicMock())
        assert isinstance(instance, InitBookAgent)


class TestSummaryAgent:
    @pytest.fixture
    def agent(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        book = _make_book(
            memory_summary="【人物卡】\n张三: 主角\n【主线进度】\n第1章: 开始（已完成）\n【伏笔清单】\n- 无\n【其他信息】\n无"
        )
        return SummaryAgent(ai_service, book, {})

    @pytest.mark.asyncio
    async def test_update_calls_api(self, agent):
        agent.ai_service.call_with_messages = AsyncMock(return_value="新摘要内容")
        result = await agent.update("第2章内容", chapter_number=2, is_last_chapter=False, chapter_title="第2章")
        assert result == "新摘要内容"

    @pytest.mark.asyncio
    async def test_update_last_chapter(self, agent):
        agent.ai_service.call_with_messages = AsyncMock(return_value="最后一章摘要")
        result = await agent.update("第5章内容", chapter_number=5, is_last_chapter=True, chapter_title="最终章")
        assert result == "最后一章摘要"

    def test_factory_can_create(self):
        instance = AgentFactory.create("summary", MagicMock(), book=MagicMock())
        assert isinstance(instance, SummaryAgent)


class TestStyleExtractorAgent:
    @pytest.fixture
    def agent(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        return StyleExtractorAgent(ai_service, global_config={})

    def test_build_prompt(self, agent):
        prompt = agent.build_prompt("这是测试文本")
        assert "测试文本" in prompt

    def test_factory_can_create(self):
        instance = AgentFactory.create("style_extractor", MagicMock())
        assert isinstance(instance, StyleExtractorAgent)


class TestAgentFactory:
    def test_register_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            AgentFactory.create("unknown", MagicMock())

    def test_list_registered_agents(self):
        registered = ["init_book", "chapter_writer", "summary", "style_extractor"]
        for name in registered:
            assert name in AgentFactory._agents
