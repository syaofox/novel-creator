import logging
from typing import Any
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.models import Book
from app.utils import prompts
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.ai_service import AiService
from app.constants import DEFAULT_SYSTEM_TEMPLATE, DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class ChapterWriterAgent(BaseAgent):
    def __init__(self, ai_service: AiService, book: Book, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service, book, global_config)

    def _get_role_prompt(self) -> str:
        system_template = self._get_config_value("system_template", DEFAULT_SYSTEM_TEMPLATE)
        memory = getattr(self.book, "memory_summary", "")
        style = getattr(self.book, "style", "") or "请根据小说的风格规范进行写作。"
        return system_template.format(memory=memory, style=style)

    def build_prompt(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        return prompts.WRITE_CHAPTER_PROMPT.format(
            chapter_number=chapter_number, core_event=core_event, prev_ending=prev_ending
        )

    def _build_messages(
        self, chapter_number: int, core_event: str, prev_ending: str
    ) -> list[ChatCompletionMessageParam]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_prompt(chapter_number, core_event, prev_ending)},
        ]

    async def write(self, chapter_number: int, core_event: str, prev_ending: str) -> str:
        messages = self._build_messages(chapter_number, core_event, prev_ending)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        top_p = self._get_config_value("top_p", DEFAULT_TOP_P)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        return await self.ai_service.call_with_messages(
            messages=messages, temperature=temperature, max_tokens=max_tokens, top_p=top_p
        )

    async def write_stream(self, chapter_number: int, core_event: str, prev_ending: str) -> AsyncGenerator[str]:
        messages = self._build_messages(chapter_number, core_event, prev_ending)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        top_p = self._get_config_value("top_p", DEFAULT_TOP_P)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        async for chunk in self.ai_service.call_with_messages_stream(
            messages=messages, temperature=temperature, max_tokens=max_tokens, top_p=top_p
        ):
            yield chunk


AgentFactory.register("chapter_writer", ChapterWriterAgent)
