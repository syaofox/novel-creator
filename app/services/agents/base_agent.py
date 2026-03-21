import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from collections.abc import AsyncGenerator

from app.constants import DEFAULT_JAILBREAK_PREFIX
from app.services.ai_service import AiService
from app.utils.ai_utils import get_config_value

if TYPE_CHECKING:
    from app.models import Book

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, ai_service: AiService, book: "Book | None" = None, global_config: dict[str, Any] | None = None):
        self.ai_service = ai_service
        self.book = book
        self.global_config = global_config or {}

    def _get_config_value(self, key: str, default: Any) -> Any:
        return get_config_value(self.book, self.global_config, key, default)

    def _get_jailbreak_prefix(self) -> str:
        return self._get_config_value("jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)

    @property
    def system_prompt(self) -> str:
        jailbreak = self._get_jailbreak_prefix()
        return (jailbreak + "\n\n" if jailbreak else "") + self._get_role_prompt()

    @abstractmethod
    def _get_role_prompt(self) -> str:
        pass

    def build_prompt(self, **kwargs) -> str:
        return ""

    async def run(self, **kwargs) -> str:
        user_prompt = self.build_prompt(**kwargs)
        return await self.ai_service.call_llm(user_prompt=user_prompt, system_prompt=self.system_prompt)

    async def run_stream(self, **kwargs) -> AsyncGenerator[str]:
        user_prompt = self.build_prompt(**kwargs)
        async for chunk in self.ai_service.call_llm_stream(user_prompt=user_prompt, system_prompt=self.system_prompt):
            yield chunk

    async def run_json(self, **kwargs) -> dict[str, Any]:
        user_prompt = self.build_prompt(**kwargs)
        result = await self.ai_service.call_llm(
            user_prompt=user_prompt,
            system_prompt=self.system_prompt + "\n请返回有效的 JSON 格式。",
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from agent result: {result[:200]}")
            return {}


class AgentFactory:
    _agents: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, name: str, agent_class: type[BaseAgent]):
        cls._agents[name] = agent_class

    @classmethod
    def create(cls, name: str, ai_service: "AiService", **kwargs) -> BaseAgent:
        if name not in cls._agents:
            raise ValueError(f"Unknown agent: {name}")
        return cls._agents[name](ai_service, **kwargs)
