import logging
from typing import TYPE_CHECKING

from app.services.agents.base_agent import BaseAgent, AgentFactory

if TYPE_CHECKING:
    from app.services.ai_service import AiService

logger = logging.getLogger(__name__)


class OutlineAgent(BaseAgent):
    def _get_role_prompt(self) -> str:
        return "你是一个专业的小说大纲专家。请根据给定的小说设定生成章节大纲。"

    def build_prompt(self, genre: str, target_chapters: int, characters: str, world_view: str) -> str:
        return f"""请生成小说大纲：
类型：{genre}
目标章节数：{target_chapters}
人物设定：{characters}
世界观设定：{world_view}
"""


AgentFactory.register("outline", OutlineAgent)
