import logging
from typing import Any

from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.services.base_ai_service import BaseAiService
from app.utils import prompts

logger = logging.getLogger(__name__)


class PlotAgent(BaseAgent):
    system_prompt = "你是一个专业的小说剧情分析专家。请分析给定的小说内容，提取剧情要点、人物动机和情节发展。"

    def build_prompt(self, chapter_content: str, chapter_number: int | None = None) -> str:
        prompt = f"请分析以下小说章节内容：\n\n{chapter_content}"
        if chapter_number:
            prompt += f"\n\n章节编号：{chapter_number}"
        return prompt

    async def extract_plot_points(self, chapter_content: str) -> list[str]:
        result = await self.run_json(action="extract_plot_points", content=chapter_content)
        return result.get("plot_points", [])

    async def analyze_conflicts(self, chapter_content: str) -> list[dict[str, str]]:
        result = await self.run_json(action="analyze_conflicts", content=chapter_content)
        return result.get("conflicts", [])


class CharacterAgent(BaseAgent):
    system_prompt = "你是一个专业的小说人物设定专家。请根据给定的小说内容，分析和塑造人物角色。"

    def build_prompt(self, basic_idea: str, genre: str, target_chapters: int) -> str:
        return f"""请根据以下创意生成人物卡：
小说类型：{genre}
目标章节数：{target_chapters}
创意：{basic_idea}
"""


class OutlineAgent(BaseAgent):
    system_prompt = "你是一个专业的小说大纲专家。请根据给定的小说设定生成章节大纲。"

    def build_prompt(self, genre: str, target_chapters: int, characters: str, world_view: str) -> str:
        return f"""请生成小说大纲：
类型：{genre}
目标章节数：{target_chapters}
人物设定：{characters}
世界观设定：{world_view}
"""


AgentFactory.register("plot", PlotAgent)
AgentFactory.register("character", CharacterAgent)
AgentFactory.register("outline", OutlineAgent)
