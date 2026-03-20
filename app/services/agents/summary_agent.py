import logging
from typing import Any
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.models import Book
from app.utils import prompts
from app.utils.ai_utils import get_config_value
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.ai_service import AiService
from app.constants import DEFAULT_JAILBREAK_PREFIX, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class SummaryAgent(BaseAgent):
    def __init__(self, ai_service: AiService, book: Book, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service)
        self.book = book
        self.global_config = global_config or {}

    def _get_config_value(self, key: str, default: Any) -> Any:
        return get_config_value(self.book, self.global_config, key, default)

    @property
    def system_prompt(self) -> str:
        jailbreak = self._get_config_value("jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
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

    def _build_messages(
        self, new_chapter_text: str, chapter_number: int, is_last_chapter: bool = True, chapter_title: str = ""
    ) -> list[ChatCompletionMessageParam]:
        next_chapter = chapter_number + 1
        return [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": self.build_prompt(
                    new_chapter=new_chapter_text,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    next_chapter=next_chapter,
                    is_last_chapter=is_last_chapter,
                ),
            },
        ]

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

        messages = self._build_messages(new_chapter_text, chapter_number, is_last_chapter, chapter_title)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        return await self.ai_service.call_with_messages(
            messages=messages, temperature=temperature, max_tokens=max_tokens
        )

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

        messages = self._build_messages(new_chapter_text, chapter_number, is_last_chapter, chapter_title)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        async for chunk in self.ai_service.call_with_messages_stream(
            messages=messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk


AgentFactory.register("summary", SummaryAgent)
