import logging
from typing import Any
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.models import Book
from app.utils import prompts
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.base_ai_service import BaseAiService
from app.constants import (
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


def _get_config_value(book: Book, global_config: dict[str, Any] | None, key: str, default: Any) -> Any:
    """获取配置值：优先使用书籍配置，其次使用全局配置，最后使用默认值"""
    book_config = book.config if book.config is not None else {}
    if key in book_config:
        return book_config[key]
    if global_config is not None and key in global_config:
        value = global_config[key]
        if key in ("temperature", "top_p"):
            return float(str(value)) if value is not None else default
        if key == "max_tokens":
            return int(value) if value is not None else default
        if key == "stream":
            return bool(int(value)) if value is not None else default
        return value
    return default


class ChapterWriterAgent(BaseAgent):
    def __init__(self, ai_service: BaseAiService, book: Book, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service)
        self.book = book
        self.global_config = global_config or {}

    @property
    def system_prompt(self) -> str:
        jailbreak = _get_config_value(self.book, self.global_config, "jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
        system_template = _get_config_value(self.book, self.global_config, "system_template", DEFAULT_SYSTEM_TEMPLATE)
        return (
            jailbreak
            + "\n\n"
            + system_template.format(
                memory=self.book.memory_summary, style=self.book.style or "请根据小说的风格规范进行写作。"
            )
        )

    def build_prompt(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        return prompts.WRITE_CHAPTER_PROMPT.format(
            chapter_number=chapter_number, core_event=core_event, prev_ending=prev_ending
        )

    async def write(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        """非流式生成章节正文"""
        user_prompt = self.build_prompt(chapter_number, core_event, prev_ending)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        temperature = _get_config_value(self.book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
        top_p = _get_config_value(self.book, self.global_config, "top_p", DEFAULT_TOP_P)
        max_tokens = _get_config_value(self.book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        response = await self.ai_service.client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def write_stream(self, chapter_number: int, core_event: str, prev_ending: str) -> AsyncGenerator[str]:
        """流式生成章节正文"""
        user_prompt = self.build_prompt(chapter_number, core_event, prev_ending)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        temperature = _get_config_value(self.book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
        top_p = _get_config_value(self.book, self.global_config, "top_p", DEFAULT_TOP_P)
        max_tokens = _get_config_value(self.book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True,
        }
        response = await self.ai_service.client.chat.completions.create(**params)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


AgentFactory.register("chapter_writer", ChapterWriterAgent)
