import logging
from typing import Any
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.constants import DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS
from app.models import Book
from app.utils.ai_utils import get_config_value, get_temperature_top_p_tokens

logger = logging.getLogger(__name__)


class AiService:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-reasoner",
        global_config: dict[str, Any] | None = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.global_config = global_config or {}

    def _get_config_value(self, key: str, default: Any) -> Any:
        return get_config_value(None, self.global_config, key, default)

    def get_config_for_book(self, book: Book | None, key: str, default: Any) -> Any:
        """获取书籍特定的配置值"""
        return get_config_value(book, self.global_config, key, default)

    def get_params_for_book(self, book: Book | None) -> tuple[float, float, int]:
        """获取书籍的 temperature, top_p, max_tokens"""
        return get_temperature_top_p_tokens(book, self.global_config)

    def _build_messages(self, system_prompt: str, user_prompt: str) -> list[ChatCompletionMessageParam]:
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    def _log_request(self, method: str, params: dict[str, Any]):
        logger.info(f"=== API 请求: {method} ===")
        logger.info(f"Model: {params.get('model')}")
        logger.info(f"Temperature: {params.get('temperature')}")
        logger.info(f"Top_p: {params.get('top_p')}")
        logger.info(f"Max_tokens: {params.get('max_tokens')}")
        logger.info(f"Stream: {params.get('stream')}")
        for i, msg in enumerate(params.get("messages", [])):
            content = msg.get("content", "")
            logger.info(f"Message[{i}] ({msg.get('role')}): {content[:200]}...")

    def _log_response(self, response: Any):
        logger.info("=== API 响应 ===")
        logger.info(f"Model: {response.model}")
        logger.info(f"Usage: {response.usage}")
        content = response.choices[0].message.content
        logger.info(f"Content: {content[:200]}...")

    async def call_llm(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        temperature = (
            temperature if temperature is not None else self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        )
        max_tokens = max_tokens if max_tokens is not None else self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)
        top_p = top_p if top_p is not None else self._get_config_value("top_p", DEFAULT_TOP_P)

        messages = self._build_messages(system_prompt, user_prompt)

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if top_p:
            params["top_p"] = top_p
        if response_format:
            params["response_format"] = response_format

        self._log_request("call_llm", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def call_llm_stream(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ) -> AsyncGenerator[str]:
        temperature = (
            temperature if temperature is not None else self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        )
        max_tokens = max_tokens if max_tokens is not None else self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)
        top_p = top_p if top_p is not None else self._get_config_value("top_p", DEFAULT_TOP_P)

        messages = self._build_messages(system_prompt, user_prompt)

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if top_p:
            params["top_p"] = top_p

        self._log_request("call_llm_stream", params)
        response = await self.client.chat.completions.create(**params)

        first_chunk = True
        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("Stream completed")

    async def call_with_messages(
        self,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        max_tokens: int,
        top_p: float = 0,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """直接传递 messages 列表的非流式调用"""
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if top_p:
            params["top_p"] = top_p
        if response_format:
            params["response_format"] = response_format

        self._log_request("call_with_messages", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def call_with_messages_stream(
        self, messages: list[ChatCompletionMessageParam], temperature: float, max_tokens: int, top_p: float = 0
    ) -> AsyncGenerator[str]:
        """直接传递 messages 列表的流式调用"""
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if top_p:
            params["top_p"] = top_p

        self._log_request("call_with_messages_stream", params)
        response = await self.client.chat.completions.create(**params)

        first_chunk = True
        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("Stream completed")
