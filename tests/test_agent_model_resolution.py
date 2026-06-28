import pytest
from unittest.mock import MagicMock

from app.services.agents.base_agent import BaseAgent
from app.services.ai_service import AiService


class _TestAgent(BaseAgent):
    AGENT_NAME = "test_agent"
    AGENT_MODEL = "deepseek-v4-flash"
    THINKING_MODE = False

    def _get_role_prompt(self) -> str:
        return ""


class _TestAgentNoName(BaseAgent):
    AGENT_NAME = None
    AGENT_MODEL = "deepseek-v4-flash"

    def _get_role_prompt(self) -> str:
        return ""


@pytest.fixture
def ai_service():
    return MagicMock(spec=AiService)


class TestBaseAgentModelResolution:
    def test_default_model_from_class(self, ai_service):
        agent = _TestAgent(ai_service)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-flash"

    def test_global_config_overrides_model(self, ai_service):
        global_config = {"agent_models": {"test_agent": "deepseek-v4-pro"}}
        agent = _TestAgent(ai_service, global_config=global_config)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-pro"

    def test_global_config_empty_dict_uses_default(self, ai_service):
        global_config = {"agent_models": {}}
        agent = _TestAgent(ai_service, global_config=global_config)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-flash"

    def test_no_agent_name_uses_class_default(self, ai_service):
        agent = _TestAgentNoName(ai_service)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-flash"

    def test_no_agent_name_ignores_global_config(self, ai_service):
        global_config = {"agent_models": {"test_agent": "deepseek-v4-pro"}}
        agent = _TestAgentNoName(ai_service, global_config=global_config)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-flash"

    def test_thinking_mode_preserved(self, ai_service):
        agent = _TestAgent(ai_service)
        kwargs = agent._get_call_kwargs()
        assert kwargs["thinking_mode"] is False

    def test_other_agent_config_does_not_affect(self, ai_service):
        global_config = {"agent_models": {"other_agent": "deepseek-v4-pro"}}
        agent = _TestAgent(ai_service, global_config=global_config)
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "deepseek-v4-flash"


class TestRealAgentDefaults:
    def test_chapter_writer_default(self, ai_service):
        from app.services.agents import ChapterWriterAgent

        agent = ChapterWriterAgent(ai_service, MagicMock())
        assert agent.AGENT_NAME == "chapter_writer"
        assert agent.AGENT_MODEL == "deepseek-v4-flash"
        assert agent.THINKING_MODE is False

    def test_summary_default(self, ai_service):
        from app.services.agents import SummaryAgent

        agent = SummaryAgent(ai_service, MagicMock())
        assert agent.AGENT_NAME == "summary"
        assert agent.AGENT_MODEL == "deepseek-v4-flash"
        assert agent.THINKING_MODE is True

    def test_init_book_default(self, ai_service):
        from app.services.agents import InitBookAgent

        agent = InitBookAgent(ai_service)
        assert agent.AGENT_NAME == "init_book"
        assert agent.AGENT_MODEL == "deepseek-v4-flash"
        assert agent.THINKING_MODE is True

    def test_style_extractor_default(self, ai_service):
        from app.services.agents import StyleExtractorAgent

        agent = StyleExtractorAgent(ai_service)
        assert agent.AGENT_NAME == "style_extractor"
        assert agent.AGENT_MODEL == "deepseek-v4-flash"
        assert agent.THINKING_MODE is True
