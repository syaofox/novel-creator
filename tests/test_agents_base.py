"""Tests for BaseAgent core methods."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.agents.base_agent import BaseAgent, AgentFactory


class ConcreteAgent(BaseAgent):
    AGENT_NAME = "test_agent"
    AGENT_MODEL = "test-model"
    THINKING_MODE = True
    REASONING_EFFORT = "high"

    def _get_role_prompt(self):
        return "You are a test agent."

    def build_prompt(self, **kwargs):
        return f"Prompt with {kwargs}"


class TestBaseAgent:
    @pytest.fixture
    def agent(self):
        ai_service = MagicMock()
        ai_service.global_config = {"agent_models": {"test_agent": "override-model"}}
        return ConcreteAgent(ai_service, global_config=ai_service.global_config)

    def test_system_prompt_with_jailbreak(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        agent = ConcreteAgent(ai_service, global_config={"jailbreak_prefix": "JB:"})
        assert agent.system_prompt.startswith("JB:")

    def test_system_prompt_without_jailbreak(self, agent):
        assert "You are a test agent." in agent.system_prompt

    def test_resolve_model_overridden(self, agent):
        model = agent._resolve_model()
        assert model == "override-model"

    def test_resolve_model_default(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        agent = ConcreteAgent(ai_service, global_config={})
        model = agent._resolve_model()
        assert model == "test-model"

    def test_get_call_kwargs(self, agent):
        kwargs = agent._get_call_kwargs()
        assert kwargs["model"] == "override-model"
        assert kwargs["thinking_mode"] is True
        assert kwargs["reasoning_effort"] == "high"

    def test_get_call_kwargs_no_overrides(self):
        ai_service = MagicMock()
        ai_service.global_config = {}

        class MinimalAgent(BaseAgent):
            AGENT_NAME = None
            AGENT_MODEL = None
            THINKING_MODE = None
            REASONING_EFFORT = None

            def _get_role_prompt(self):
                return "role"

        agent = MinimalAgent(ai_service, global_config={})
        kwargs = agent._get_call_kwargs()
        assert kwargs == {}

    def test_get_config_value(self, agent):
        assert agent._get_config_value("nonexistent", "default") == "default"

    @pytest.mark.asyncio
    async def test_run_calls_ai_service(self, agent):
        agent.ai_service.call_llm = AsyncMock(return_value="response")
        result = await agent.run(user_input="test")
        assert result == "response"
        agent.ai_service.call_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_stream(self, agent):
        async def async_gen():
            yield "chunk1"
            yield "chunk2"

        agent.ai_service.call_llm_stream = MagicMock(return_value=async_gen())
        chunks = []
        async for chunk in agent.run_stream(user_input="test"):
            chunks.append(chunk)
        assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_run_json_success(self, agent):
        agent.ai_service.call_llm = AsyncMock(return_value='{"key": "value"}')
        result = await agent.run_json(user_input="test")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_run_json_failure_returns_empty(self, agent):
        agent.ai_service.call_llm = AsyncMock(return_value="not json")
        result = await agent.run_json(user_input="test")
        assert result == {}

    @pytest.mark.asyncio
    async def test_run_json_calls_with_json_format(self, agent):
        agent.ai_service.call_llm = AsyncMock(return_value="{}")
        await agent.run_json(user_input="test")
        call_kwargs = agent.ai_service.call_llm.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}


class TestAgentFactory:
    def test_create_known_agent(self):
        AgentFactory._agents["test_agent"] = ConcreteAgent
        instance = AgentFactory.create("test_agent", MagicMock())
        assert isinstance(instance, ConcreteAgent)

    def test_create_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            AgentFactory.create("unknown", MagicMock())

    def test_register_and_create(self):
        AgentFactory.register("new_agent", ConcreteAgent)
        instance = AgentFactory.create("new_agent", MagicMock())
        assert isinstance(instance, ConcreteAgent)
