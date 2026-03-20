import logging
from collections.abc import AsyncGenerator

from app.constants import DEFAULT_JAILBREAK_PREFIX
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.utils.ai_utils import get_config_value

logger = logging.getLogger(__name__)

_EXTRACT_STYLE_PROMPT = (
    "请分析以下文字片段的写作风格，并以结构化条目给出详细的风格规范描述。\n"
    "输出格式要求：第一行为「标题: 文风名称」，空一行后列出风格特征条目。例如：\n"
    "标题: 简洁干练\n\n"
    "1. 短句为主，节奏明快\n"
    "2. 多用白描手法\n"
    "3. ..."
)


class StyleExtractorAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        jailbreak = get_config_value(None, self.ai_service.global_config, "jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
        return (
            jailbreak + "\n\n" + "你是一个专业的小说写作风格分析专家。"
            "请分析给定的文字片段，提取其写作风格特征，"
            "包括但不限于：句式特点、修辞手法、节奏韵律、"
            "用词偏好、叙事视角、情感基调、场景描写方式等。"
        )

    def build_prompt(self, text: str) -> str:
        return f"{_EXTRACT_STYLE_PROMPT}\n\n{text}"

    async def extract_style(self, text: str) -> dict:
        return await self.run_json(text=text)

    def stream_extract_style(self, text: str) -> AsyncGenerator[str]:
        return self.run_stream(text=text)


AgentFactory.register("style_extractor", StyleExtractorAgent)
