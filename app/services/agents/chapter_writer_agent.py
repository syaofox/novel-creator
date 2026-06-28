import logging
import re
from typing import Any
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.repositories.file_repository import Book
from app.utils import prompts
from app.utils.ai_utils import extract_dynamic_sections, extract_stable_sections
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.ai_service import AiService
from app.constants import DEFAULT_SYSTEM_TEMPLATE, DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class ChapterWriterAgent(BaseAgent):
    AGENT_NAME = "chapter_writer"
    AGENT_MODEL = "deepseek-v4-flash"
    THINKING_MODE = False

    def __init__(self, ai_service: AiService, book: Book, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service, book, global_config)

    def _get_role_prompt(self) -> str:
        system_template = self._get_config_value("system_template", DEFAULT_SYSTEM_TEMPLATE)
        style = getattr(self.book, "style", "") or "请根据小说的风格规范进行写作。"
        base = system_template.format(style=style)

        memory_summary = getattr(self.book, "memory_summary", "") or ""
        stable = extract_stable_sections(memory_summary)
        if stable:
            base = base + "\n\n" + stable

        return base

    def build_prompt(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        return prompts.WRITE_CHAPTER_PROMPT.format(
            chapter_number=chapter_number, core_event=core_event, prev_ending=prev_ending
        )

    def _build_user_content(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        memory_summary = getattr(self.book, "memory_summary", "") or ""
        dynamic = extract_dynamic_sections(memory_summary)
        parts = []
        if dynamic:
            parts.append(dynamic)
        parts.append(self.build_prompt(chapter_number, core_event, prev_ending))
        return "\n\n".join(parts)

    def _build_messages(
        self, chapter_number: int, core_event: str, prev_ending: str
    ) -> list[ChatCompletionMessageParam]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._build_user_content(chapter_number, core_event, prev_ending)},
        ]

    async def write(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        messages = self._build_messages(chapter_number, core_event, prev_ending)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        top_p = self._get_config_value("top_p", DEFAULT_TOP_P)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        return await self.ai_service.call_with_messages(
            messages=messages, temperature=temperature, max_tokens=max_tokens, top_p=top_p,
            **self._get_call_kwargs(),
        )

    async def write_stream(self, chapter_number: int, core_event: str, prev_ending: str) -> AsyncGenerator[str]:
        messages = self._build_messages(chapter_number, core_event, prev_ending)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        top_p = self._get_config_value("top_p", DEFAULT_TOP_P)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        async for chunk in self.ai_service.call_with_messages_stream(
            messages=messages, temperature=temperature, max_tokens=max_tokens, top_p=top_p,
            **self._get_call_kwargs(),
        ):
            yield chunk


AgentFactory.register("chapter_writer", ChapterWriterAgent)
