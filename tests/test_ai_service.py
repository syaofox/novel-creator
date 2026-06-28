import pytest
from unittest.mock import MagicMock, AsyncMock
from app.utils.ai_utils import extract_json, get_config_value
from app.services.ai_service import AiService, _build_extra_body
from app.constants import DEFAULT_MODEL, DEFAULT_MODEL_FLASH, DEFAULT_REASONING_EFFORT, MAX_TOKENS_LIMIT, DEFAULT_MAX_TOKENS


class TestBuildExtraBody:
    def test_thinking_enabled(self):
        result = _build_extra_body(thinking_mode=True)
        assert result == {"thinking": {"type": "enabled"}}

    def test_thinking_disabled(self):
        result = _build_extra_body(thinking_mode=False)
        assert result == {"thinking": {"type": "disabled"}}

    def test_thinking_none(self):
        result = _build_extra_body(thinking_mode=None)
        assert result == {}

    def test_all_none(self):
        result = _build_extra_body(thinking_mode=None)
        assert result == {}


class TestAiServiceDefaults:
    def test_default_base_url(self):
        assert AiService(api_key="test").client.base_url == "https://api.deepseek.com"

    def test_default_model(self):
        service = AiService(api_key="test")
        assert service.model == DEFAULT_MODEL

    def test_default_model_is_v4_pro(self):
        assert DEFAULT_MODEL == "deepseek-v4-pro"

    def test_default_model_flash(self):
        assert DEFAULT_MODEL_FLASH == "deepseek-v4-flash"

    def test_default_reasoning_effort(self):
        assert DEFAULT_REASONING_EFFORT == "high"

    def test_max_tokens_limit(self):
        assert MAX_TOKENS_LIMIT == 384000

    def test_default_max_tokens(self):
        assert DEFAULT_MAX_TOKENS == 16384


class TestAiServiceCallLlm:
    @pytest.fixture
    def service(self):
        svc = AiService(api_key="test-key")
        svc.client.chat.completions.create = AsyncMock()
        svc.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="test response"))],
            model="deepseek-v4-pro",
            usage=None,
        )
        return svc

    async def test_model_override(self, service):
        result = await service.call_llm(user_prompt="hello", model="deepseek-v4-flash")
        assert result == "test response"
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "deepseek-v4-flash"

    async def test_default_model_used(self, service):
        await service.call_llm(user_prompt="hello")
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == DEFAULT_MODEL

    async def test_thinking_mode_enabled(self, service):
        await service.call_llm(user_prompt="hello", thinking_mode=True, reasoning_effort="high")
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
        assert call_kwargs["reasoning_effort"] == "high"

    async def test_thinking_mode_disabled(self, service):
        await service.call_llm(user_prompt="hello", thinking_mode=False, reasoning_effort=None)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
        assert "reasoning_effort" not in call_kwargs

    async def test_thinking_mode_none(self, service):
        await service.call_llm(user_prompt="hello", thinking_mode=None, reasoning_effort=None)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "extra_body" not in call_kwargs
        assert "reasoning_effort" not in call_kwargs

    async def test_response_format_preserved(self, service):
        fmt = {"type": "json_object"}
        await service.call_llm(user_prompt="hello", response_format=fmt, thinking_mode=True)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == fmt
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


class TestAiServiceCallWithMessages:
    @pytest.fixture
    def service(self):
        svc = AiService(api_key="test-key")
        svc.client.chat.completions.create = AsyncMock()
        svc.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="test response"))],
            model="deepseek-v4-pro",
            usage=None,
        )
        return svc

    async def test_model_override(self, service):
        messages = [{"role": "user", "content": "hello"}]
        await service.call_with_messages(
            messages=messages, temperature=0.7, max_tokens=4096, model="deepseek-v4-flash"
        )
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "deepseek-v4-flash"

    async def test_thinking_with_reasoning(self, service):
        messages = [{"role": "user", "content": "hello"}]
        await service.call_with_messages(
            messages=messages, temperature=0.7, max_tokens=4096,
            thinking_mode=True, reasoning_effort="max",
        )
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
        assert call_kwargs["reasoning_effort"] == "max"

    async def test_no_extra_when_none(self, service):
        messages = [{"role": "user", "content": "hello"}]
        await service.call_with_messages(
            messages=messages, temperature=0.7, max_tokens=4096,
            thinking_mode=None, reasoning_effort=None,
        )
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "extra_body" not in call_kwargs


class TestAiServiceCallLlmStream:
    @pytest.fixture
    def service(self):
        svc = AiService(api_key="test-key")
        svc.client.chat.completions.create = AsyncMock()

        chunk1 = MagicMock()
        chunk1.model = "deepseek-v4-pro"
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "chunk"
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = None
        chunk2.choices[0].finish_reason = "stop"
        chunk2.usage = None

        async def async_iter():
            yield chunk1
            yield chunk2

        svc.client.chat.completions.create.return_value = async_iter()
        return svc

    async def test_stream_model_override(self, service):
        results = []
        async for c in service.call_llm_stream(user_prompt="hello", model="deepseek-v4-flash"):
            results.append(c)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "deepseek-v4-flash"
        assert call_kwargs["stream"] is True

    async def test_stream_thinking_mode(self, service):
        results = []
        async for c in service.call_llm_stream(
            user_prompt="hello", thinking_mode=True, reasoning_effort="high"
        ):
            results.append(c)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
        assert call_kwargs["reasoning_effort"] == "high"


class TestAiServiceCallWithMessagesStream:
    @pytest.fixture
    def service(self):
        svc = AiService(api_key="test-key")
        svc.client.chat.completions.create = AsyncMock()

        chunk1 = MagicMock()
        chunk1.model = "deepseek-v4-pro"
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "msg"
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = None
        chunk2.choices[0].finish_reason = "stop"
        chunk2.usage = None

        async def async_iter():
            yield chunk1
            yield chunk2

        svc.client.chat.completions.create.return_value = async_iter()
        return svc

    async def test_messages_stream_model_override(self, service):
        messages = [{"role": "user", "content": "hello"}]
        results = []
        async for c in service.call_with_messages_stream(
            messages=messages, temperature=0.7, max_tokens=4096, model="deepseek-v4-flash"
        ):
            results.append(c)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "deepseek-v4-flash"

    async def test_messages_stream_thinking(self, service):
        messages = [{"role": "user", "content": "hello"}]
        results = []
        async for c in service.call_with_messages_stream(
            messages=messages, temperature=0.7, max_tokens=4096,
            thinking_mode=True, reasoning_effort="max",
        ):
            results.append(c)
        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
        assert call_kwargs["reasoning_effort"] == "max"


class TestExtractJson:
    def test_valid_json(self):
        content = '{"key": "value"}'
        result = extract_json(content)
        assert result == content

    def test_json_with_extra_whitespace(self):
        content = '  {"key": "value"}  '
        result = extract_json(content)
        assert result == content

    def test_json_block(self):
        content = """
Some text before
```json
{"key": "value"}
```
Some text after
"""
        result = extract_json(content)
        assert result == '{"key": "value"}'

    def test_multiple_json_blocks(self):
        content = """
```json
{"invalid": true}
```
```json
{"valid": true}
"""
        result = extract_json(content)
        assert result == '{"invalid": true}'

    def test_json_in_text(self):
        content = 'Some text {"key": "value"} more text'
        result = extract_json(content)
        assert result == '{"key": "value"}'

    def test_no_json_returns_original(self):
        content = "No JSON here"
        result = extract_json(content)
        assert result == "No JSON here"


class TestGetConfigValue:
    def test_book_config_priority(self):
        mock_book = MagicMock()
        mock_book.config = {"temperature": 0.5}
        global_config = {"temperature": 0.7}

        result = get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.5

    def test_global_config_fallback(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"temperature": 0.7}

        result = get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.7

    def test_default_value(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {}

        result = get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.8

    def test_none_book_config(self):
        mock_book = MagicMock()
        mock_book.config = None
        global_config = {"temperature": 0.7}

        result = get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.7

    def test_string_to_float(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"temperature": "0.9"}

        result = get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.9
        assert isinstance(result, float)

    def test_string_to_int(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"max_tokens": "4096"}

        result = get_config_value(mock_book, global_config, "max_tokens", 16384)
        assert result == 4096
        assert isinstance(result, int)

    def test_stream_conversion(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"stream": 1}

        result = get_config_value(mock_book, global_config, "stream", False)
        assert result is True

    def test_stream_zero_returns_false(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"stream": 0}

        result = get_config_value(mock_book, global_config, "stream", True)
        assert result is False
