import logging
from typing import Any
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.models import Book
from app.utils import prompts
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.base_ai_service import BaseAiService
from app.constants import DEFAULT_JAILBREAK_PREFIX, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

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


class SummaryAgent(BaseAgent):
    def __init__(self, ai_service: BaseAiService, book: Book, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service)
        self.book = book
        self.global_config = global_config or {}

    @property
    def system_prompt(self) -> str:
        jailbreak = _get_config_value(self.book, self.global_config, "jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
        return jailbreak + "\n\n" + prompts.UPDATE_SUMMARY_SYSTEM_PROMPT

    def build_prompt(
        self,
        new_chapter: str,
        chapter_number: int,
        chapter_title: str = "",
        next_chapter: int | None = None,
        is_last_chapter: bool = True,
    ) -> str:
        if is_last_chapter:
            return prompts.UPDATE_SUMMARY_PROMPT_LAST.format(
                old_summary=self.book.memory_summary,
                new_chapter=new_chapter,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
            )
        else:
            return prompts.UPDATE_SUMMARY_PROMPT.format(
                old_summary=self.book.memory_summary,
                new_chapter=new_chapter,
                chapter_number=chapter_number,
                next_chapter=next_chapter,
                chapter_title=chapter_title,
            )

    async def update(
        self,
        new_chapter_text: str,
        chapter_number: int | None = None,
        is_last_chapter: bool = True,
        chapter_title: str = "",
    ) -> str:
        """非流式生成新摘要"""
        if chapter_number is None:
            chapter_number = int(self.book.current_chapter) if self.book.current_chapter else 1
        next_chapter = chapter_number + 1

        user_prompt = self.build_prompt(
            new_chapter=new_chapter_text,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            next_chapter=next_chapter,
            is_last_chapter=is_last_chapter,
        )

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        temperature = _get_config_value(self.book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
        max_tokens = _get_config_value(self.book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = await self.ai_service.client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def update_stream(
        self,
        new_chapter_text: str,
        chapter_number: int | None = None,
        is_last_chapter: bool = True,
        chapter_title: str = "",
    ) -> AsyncGenerator[str]:
        """流式生成新摘要"""
        if chapter_number is None:
            chapter_number = int(self.book.current_chapter) if self.book.current_chapter else 1
        next_chapter = chapter_number + 1

        user_prompt = self.build_prompt(
            new_chapter=new_chapter_text,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            next_chapter=next_chapter,
            is_last_chapter=is_last_chapter,
        )

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        temperature = _get_config_value(self.book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
        max_tokens = _get_config_value(self.book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        response = await self.ai_service.client.chat.completions.create(**params)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


AgentFactory.register("summary", SummaryAgent)
