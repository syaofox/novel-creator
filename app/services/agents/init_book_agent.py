import json
import logging
from typing import Any, cast
from collections.abc import AsyncGenerator

from openai.types.chat import ChatCompletionMessageParam

from app.repositories.file_repository import Book
from app.utils import prompts
from app.utils.ai_utils import get_config_value, extract_json, parse_marked_content
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.ai_service import AiService
from app.constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class InitBookAgent(BaseAgent):
    AGENT_NAME = "init_book"
    AGENT_MODEL = "deepseek-v4-flash"
    THINKING_MODE = True

    def __init__(self, ai_service: AiService, book: Book | None = None, global_config: dict[str, Any] | None = None):
        super().__init__(ai_service, book, global_config)
        self._style_section = ""
        self._jailbreak_override = ""

    def with_jailbreak(self, jailbreak_prefix: str = "") -> "InitBookAgent":
        self._jailbreak_override = jailbreak_prefix
        return self

    def _get_jailbreak_prefix(self) -> str:
        if self._jailbreak_override:
            return self._jailbreak_override
        return super()._get_jailbreak_prefix()

    def with_style(self, style: str = "") -> "InitBookAgent":
        self._style_section = (
            f"\n\n【用户指定的风格规范】\n{style}\n\n请在生成人物卡和大纲时充分考虑用户的风格偏好。" if style else "\n"
        )
        return self

    def _get_role_prompt(self) -> str:
        return prompts.INIT_BOOK_SYSTEM_PROMPT.format(target_chapters=0, style_section=self._style_section)

    def _build_system_prompt(self, target_chapters: int) -> str:
        jailbreak = self._get_jailbreak_prefix()
        return (jailbreak + "\n\n" if jailbreak else "") + prompts.INIT_BOOK_SYSTEM_PROMPT.format(
            target_chapters=target_chapters, style_section=self._style_section
        )

    def build_prompt(self, basic_idea: str, genre: str, target_chapters: int) -> str:
        return f"""用户创意：{basic_idea}
小说类型：{genre}
目标章节数：{target_chapters}"""

    def _build_messages(self, basic_idea: str, genre: str, target_chapters: int) -> list[ChatCompletionMessageParam]:
        system_content = self._build_system_prompt(target_chapters)
        user_prompt = self.build_prompt(basic_idea, genre, target_chapters)

        return [{"role": "system", "content": system_content}, {"role": "user", "content": user_prompt}]

    async def initialize(self, basic_idea: str, genre: str, target_chapters: int) -> dict[str, str]:
        messages = self._build_messages(basic_idea, genre, target_chapters)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        content = await self.ai_service.call_with_messages(
            messages=messages, temperature=temperature, max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **self._get_call_kwargs(),
        )

        if not content:
            return {"characters": "", "world_view": "", "style": "", "outline": "", "foreshadowing": "", "other": ""}

        try:
            json_str = extract_json(content)
            data = json.loads(json_str)
            result = cast(dict[str, str], data)
            required_fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
            for field in required_fields:
                if field not in result:
                    result[field] = ""
            return result
        except json.JSONDecodeError:
            logger.warning(f"无法解析 API 返回的 JSON，尝试解析标记格式，原始内容：{content[:500]}...")
            parsed = parse_marked_content(content)
            if any(parsed.values()):
                required_fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
                for field in required_fields:
                    if field not in parsed:
                        parsed[field] = ""
                return parsed
            return {
                "characters": content,
                "world_view": "",
                "style": "",
                "outline": "",
                "foreshadowing": "",
                "other": "",
            }

    async def stream_initialize(
        self, basic_idea: str, genre: str, target_chapters: int
    ) -> AsyncGenerator[dict[str, str]]:
        messages = self._build_messages(basic_idea, genre, target_chapters)
        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        async for chunk in self.ai_service.call_with_messages_stream(
            messages=messages, temperature=temperature, max_tokens=max_tokens,
            **self._get_call_kwargs(),
        ):
            yield {"content": chunk}


AgentFactory.register("init_book", InitBookAgent)
