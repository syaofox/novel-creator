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

    # ── book-level override tests ──

    def _mock_book(self, **config_overrides) -> MagicMock:
        from app.repositories.file_repository import Book
        book = MagicMock(spec=Book)
        book.config = dict(config_overrides)
        return book

    def test_book_override_takes_precedence_over_global(self):
        book = self._mock_book(chapter_writer_user_prompt="book-level prompt {chapter_number}")
        global_config = {"agent_prompts": {"chapter_writer_user_prompt": "global prompt"}}
        result = get_agent_prompt(global_config, "chapter_writer_user_prompt", book)
        assert result == "book-level prompt {chapter_number}"

    def test_book_override_precedes_default(self):
        book = self._mock_book(summary_system_prompt="book summary prompt")
        result = get_agent_prompt(None, "summary_system_prompt", book)
        assert result == "book summary prompt"

    def test_global_config_used_when_book_has_no_key(self):
        book = self._mock_book(temperature=0.5)
        global_config = {"agent_prompts": {"chapter_writer_user_prompt": "global fallback"}}
        result = get_agent_prompt(global_config, "chapter_writer_user_prompt", book)
        assert result == "global fallback"

    def test_default_used_when_neither_book_nor_global_has_key(self):
        book = self._mock_book(temperature=0.5)
        result = get_agent_prompt(None, "chapter_writer_user_prompt", book)
        assert "{chapter_number}" in result

    def test_book_empty_string_falls_through(self):
        book = self._mock_book(chapter_writer_user_prompt="")
        result = get_agent_prompt(None, "chapter_writer_user_prompt", book)
        assert "{chapter_number}" in result

    def test_book_none_config(self):
        book = self._mock_book()
        book.config = None
        result = get_agent_prompt(None, "chapter_writer_user_prompt", book)
        assert "{chapter_number}" in result


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
