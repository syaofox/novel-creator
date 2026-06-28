import logging

from app.services.agents.base_agent import BaseAgent, AgentFactory
from app.utils.ai_utils import get_agent_prompt

logger = logging.getLogger(__name__)


class StyleExtractorAgent(BaseAgent):
    AGENT_NAME = "style_extractor"
    AGENT_MODEL = "deepseek-v4-flash"
    THINKING_MODE = True

    def _get_role_prompt(self) -> str:
        return get_agent_prompt(self.global_config, "style_extractor_system_prompt")

    def build_prompt(self, text: str) -> str:
        user_prompt = get_agent_prompt(self.global_config, "style_extractor_user_prompt")
        return f"{user_prompt}\n\n{text}"

    async def extract_style(self, text: str) -> dict:
        return await self.run_json(text=text)


AgentFactory.register("style_extractor", StyleExtractorAgent)
