import logging
from typing import TYPE_CHECKING

from app.services.agents.base_agent import BaseAgent, AgentFactory

if TYPE_CHECKING:
    from app.services.ai_service import AiService

logger = logging.getLogger(__name__)


class CharacterAgent(BaseAgent):
    def _get_role_prompt(self) -> str:
        return "你是一个专业的小说人物设定专家。请根据给定的小说内容，分析和塑造人物角色。"

    def build_prompt(self, basic_idea: str, genre: str, target_chapters: int) -> str:
        return f"""请根据以下创意生成人物卡：
小说类型：{genre}
目标章节数：{target_chapters}
创意：{basic_idea}
"""


AgentFactory.register("character", CharacterAgent)
