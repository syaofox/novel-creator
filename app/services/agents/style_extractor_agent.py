import logging

from app.constants import DEFAULT_JAILBREAK_PREFIX
from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.utils.ai_utils import get_config_value

logger = logging.getLogger(__name__)


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
        return f"请分析以下文字片段的写作风格，并以结构化条目给出详细的风格规范描述：\n\n{text}"

    async def extract_style(self, text: str) -> dict:
        return await self.run_json(text=text)


AgentFactory.register("style_extractor", StyleExtractorAgent)
