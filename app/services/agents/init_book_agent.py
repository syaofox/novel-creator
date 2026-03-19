import json
import logging
import re
from typing import Any, cast

from app.models import Book
from app.utils import prompts
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.base_ai_service import BaseAiService
from app.constants import DEFAULT_JAILBREAK_PREFIX, DEFAULT_SYSTEM_TEMPLATE, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


def _extract_json(content: str) -> str:
    """从可能包含额外文本的内容中提取 JSON 字符串"""
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass

    json_block_pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(json_block_pattern, content, re.DOTALL)
    if matches:
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidate = content[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    return content


def _parse_marked_content(content: str) -> dict[str, str]:
    """解析标记格式的内容，提取各个字段"""
    fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
    result = {}

    for field in fields:
        field_marker = f"【{field}】"
        start_idx = content.find(field_marker)
        if start_idx == -1:
            result[field] = ""
            continue

        end_marker = f"【{field}】"
        end_idx = content.find(end_marker, start_idx + len(field_marker))

        if end_idx != -1:
            field_content = content[start_idx + len(field_marker) : end_idx].strip()
            result[field] = field_content
        else:
            next_marker_pos = -1
            for other_field in fields:
                if other_field == field:
                    continue
                marker = f"【{other_field}】"
                pos = content.find(marker, start_idx + len(field_marker))
                if pos != -1 and (next_marker_pos == -1 or pos < next_marker_pos):
                    next_marker_pos = pos

            if next_marker_pos != -1:
                field_content = content[start_idx + len(field_marker) : next_marker_pos].strip()
                result[field] = field_content
            else:
                field_content = content[start_idx + len(field_marker) :].strip()
                result[field] = field_content

    return result


class InitBookAgent(BaseAgent):
    def __init__(
        self, ai_service: BaseAiService, book: Book | None = None, global_config: dict[str, Any] | None = None
    ):
        super().__init__(ai_service)
        self.book = book
        self.global_config = global_config or {}
        self._jailbreak_prefix = ""
        self._style_section = ""

    def with_jailbreak(self, jailbreak_prefix: str = "") -> "InitBookAgent":
        self._jailbreak_prefix = jailbreak_prefix
        return self

    def with_style(self, style: str = "") -> "InitBookAgent":
        self._style_section = (
            f"\n\n【用户指定的风格规范】\n{style}\n\n请在生成人物卡和大纲时充分考虑用户的风格偏好。" if style else "\n"
        )
        return self

    @property
    def system_prompt(self) -> str:
        jailbreak = self._jailbreak_prefix
        return ((jailbreak + "\n\n") if jailbreak else "") + prompts.INIT_BOOK_SYSTEM_PROMPT.format(
            target_chapters=0, style_section=self._style_section
        )

    def build_prompt(self, basic_idea: str, genre: str, target_chapters: int) -> str:
        return f"""用户创意：{basic_idea}
小说类型：{genre}
目标章节数：{target_chapters}"""

    async def initialize(self, basic_idea: str, genre: str, target_chapters: int) -> dict[str, str]:
        """初始化书籍，返回解析后的数据"""
        from openai.types.chat import ChatCompletionMessageParam

        system_content = (
            (self._jailbreak_prefix + "\n\n") if self._jailbreak_prefix else ""
        ) + prompts.INIT_BOOK_SYSTEM_PROMPT.format(target_chapters=target_chapters, style_section="")
        user_prompt = self.build_prompt(basic_idea, genre, target_chapters)

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        response = await self.ai_service.client.chat.completions.create(**params)
        content = response.choices[0].message.content

        if content is None:
            return {"characters": "", "world_view": "", "style": "", "outline": "", "foreshadowing": "", "other": ""}

        try:
            json_str = _extract_json(content)
            data = json.loads(json_str)
            result = cast(dict[str, str], data)
            required_fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
            for field in required_fields:
                if field not in result:
                    result[field] = ""
            return result
        except json.JSONDecodeError:
            logger.warning(f"无法解析 API 返回的 JSON，尝试解析标记格式，原始内容：{content[:500]}...")
            parsed = _parse_marked_content(content)
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

    async def stream_initialize(self, basic_idea: str, genre: str, target_chapters: int):
        """流式初始化小说，直接返回原始内容块"""
        from openai.types.chat import ChatCompletionMessageParam

        system_content = (
            (self._jailbreak_prefix + "\n\n") if self._jailbreak_prefix else ""
        ) + prompts.INIT_BOOK_SYSTEM_PROMPT.format(target_chapters=target_chapters, style_section=self._style_section)
        user_prompt = self.build_prompt(basic_idea, genre, target_chapters)

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        temperature = self._get_config_value("temperature", DEFAULT_TEMPERATURE)
        max_tokens = self._get_config_value("max_tokens", DEFAULT_MAX_TOKENS)

        params = {
            "model": self.ai_service.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = await self.ai_service.client.chat.completions.create(**params, stream=True)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield {"content": chunk.choices[0].delta.content}

    def _get_config_value(self, key: str, default: Any) -> Any:
        """获取配置值：优先使用书籍配置，其次使用全局配置，最后使用默认值"""
        if self.book:
            book_config = self.book.config if self.book.config is not None else {}
            if key in book_config:
                return book_config[key]

        if key in self.global_config:
            value = self.global_config[key]
            if key in ("temperature", "top_p"):
                return float(str(value)) if value is not None else default
            if key == "max_tokens":
                return int(value) if value is not None else default
            return value

        return default


AgentFactory.register("init_book", InitBookAgent)
