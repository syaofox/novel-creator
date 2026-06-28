import pytest
from unittest.mock import MagicMock

from app.utils.ai_utils import get_agent_prompt, PROMPT_DEFAULTS
from app.services.agents.base_agent import BaseAgent
from app.services.ai_service import AiService


class _PromptTestAgent(BaseAgent):
    AGENT_NAME = "test_agent"
    AGENT_MODEL = "deepseek-v4-flash"

    def _get_role_prompt(self) -> str:
        return get_agent_prompt(self.global_config, "summary_system_prompt")

    def build_prompt(self, **kwargs) -> str:
        return get_agent_prompt(self.global_config, "summary_user_prompt")


@pytest.fixture
def ai_service():
    return MagicMock(spec=AiService)


class TestGetAgentPrompt:
    def test_returns_default_when_no_config(self):
        result = get_agent_prompt(None, "chapter_writer_user_prompt")
        assert "{chapter_number}" in result
        assert "{core_event}" in result

    def test_returns_default_when_no_agent_prompts(self):
        result = get_agent_prompt({}, "chapter_writer_user_prompt")
        assert "{chapter_number}" in result

    def test_returns_default_when_key_missing(self):
        result = get_agent_prompt({"agent_prompts": {}}, "chapter_writer_user_prompt")
        assert "{chapter_number}" in result

    def test_returns_custom_value_when_set(self):
        global_config = {"agent_prompts": {"chapter_writer_user_prompt": "custom prompt {chapter_number}"}}
        result = get_agent_prompt(global_config, "chapter_writer_user_prompt")
        assert result == "custom prompt {chapter_number}"

    def test_unknown_key_returns_empty(self):
        result = get_agent_prompt({}, "non_existent_key")
        assert result == ""

    def test_prompt_defaults_contains_all_keys(self):
        expected_keys = [
            "system_template", "jailbreak_prefix",
            "chapter_writer_user_prompt", "summary_system_prompt",
            "summary_user_prompt", "summary_user_prompt_last",
            "init_book_system_prompt", "init_book_user_prompt",
            "style_extractor_system_prompt", "style_extractor_user_prompt",
        ]
        for key in expected_keys:
            assert key in PROMPT_DEFAULTS, f"Missing default for {key}"
            assert PROMPT_DEFAULTS[key], f"Empty default for {key}"


class TestAgentUsesConfigPrompts:
    def test_summary_system_prompt_from_config(self, ai_service):
        custom_prompt = "custom summary system prompt"
        global_config = {"agent_prompts": {"summary_system_prompt": custom_prompt}}
        agent = _PromptTestAgent(ai_service, global_config=global_config)
        assert agent._get_role_prompt() == custom_prompt

    def test_summary_system_prompt_default(self, ai_service):
        agent = _PromptTestAgent(ai_service)
        assert agent._get_role_prompt() == PROMPT_DEFAULTS["summary_system_prompt"]

    def test_build_prompt_from_config(self, ai_service):
        custom_user = "custom user {old_summary}"
        global_config = {"agent_prompts": {"summary_user_prompt": custom_user}}
        agent = _PromptTestAgent(ai_service, global_config=global_config)
        result = agent.build_prompt(old_summary="test")
        assert agent.build_prompt() == custom_user

    def test_build_prompt_default(self, ai_service):
        agent = _PromptTestAgent(ai_service)
        assert agent.build_prompt() == PROMPT_DEFAULTS["summary_user_prompt"]
