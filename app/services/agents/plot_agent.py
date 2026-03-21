import logging
from typing import TYPE_CHECKING

from app.services.agents.base_agent import BaseAgent, AgentFactory

if TYPE_CHECKING:
    from app.services.ai_service import AiService

logger = logging.getLogger(__name__)


class PlotAgent(BaseAgent):
    def _get_role_prompt(self) -> str:
        return "你是一个专业的小说剧情分析专家。请分析给定的小说内容，提取剧情要点、人物动机和情节发展。"

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


AgentFactory.register("plot", PlotAgent)
