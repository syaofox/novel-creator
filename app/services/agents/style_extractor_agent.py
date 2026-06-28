import logging

from app.services.agents.base_agent import BaseAgent, AgentFactory

logger = logging.getLogger(__name__)

_EXTRACT_STYLE_PROMPT = (
    "请以 JSON 格式分析以下文字片段的写作风格。\n"
    "要求：\n"
    '- "title"：为这种风格取一个简洁准确的名称（2-6个字）\n'
    '- "content"：详细描述该风格的各个特征，每一条独立成行\n'
    '示例：{"title": "简洁干练", "content": "1. 短句为主，节奏明快\\n2. 多用白描手法\\n3. 叙事直白精炼"}'
)


class StyleExtractorAgent(BaseAgent):
    AGENT_NAME = "style_extractor"
    AGENT_MODEL = "deepseek-v4-flash"
    THINKING_MODE = True

    def _get_role_prompt(self) -> str:
        return (
            "你是一个专业的小说写作风格分析专家。"
            "请分析给定的文字片段，提取其写作风格特征，"
            "包括但不限于：句式特点、修辞手法、节奏韵律、"
            "用词偏好、叙事视角、情感基调、场景描写方式等。"
        )

    def build_prompt(self, text: str) -> str:
        return f"{_EXTRACT_STYLE_PROMPT}\n\n{text}"

    async def extract_style(self, text: str) -> dict:
        return await self.run_json(text=text)


AgentFactory.register("style_extractor", StyleExtractorAgent)
