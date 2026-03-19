import json
import logging
import re
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
)
from app.models import Book
from app.utils import prompts

logger = logging.getLogger(__name__)


def _get_config_value(book: Book, global_config: dict[str, Any] | None, key: str, default: Any) -> Any:
    """获取配置值：优先使用书籍配置，其次使用全局配置，最后使用默认值"""
    book_config = book.config if book.config is not None else {}  # type: ignore
    if key in book_config:
        return book_config[key]
    if global_config is not None and key in global_config:
        value = global_config[key]
        if key in ("temperature", "top_p"):
            return float(str(value)) if value is not None else default
        if key == "max_tokens":
            return int(value) if value is not None else default
        if key == "stream":
            return bool(int(value)) if value is not None else default
        return value
    return default


def _extract_json(content: str) -> str:
    """从可能包含额外文本的内容中提取 JSON 字符串"""
    # 尝试直接解析
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    json_block_pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(json_block_pattern, content, re.DOTALL)
    if matches:
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    # 尝试提取第一个 { 和最后一个 } 之间的内容
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidate = content[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 如果都不行，返回原始内容
    return content


def _parse_marked_content(content: str) -> dict[str, str]:
    """解析标记格式的内容，提取各个字段

    格式示例：
    【characters】...【characters】
    【world_view】...【world_view】
    也支持前缀如：[Pasted ~24 【characters】...
    """
    # 定义可能的字段名
    fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
    result = {}

    for field in fields:
        field_marker = f"【{field}】"
        # 方法1：查找成对标记（允许标记前有任意文本）
        # 查找第一个开始标记
        start_idx = content.find(field_marker)
        if start_idx == -1:
            result[field] = ""
            continue

        # 查找结束标记（从开始标记之后开始搜索）
        end_marker = f"【{field}】"
        end_idx = content.find(end_marker, start_idx + len(field_marker))

        if end_idx != -1:
            # 找到成对标记
            field_content = content[start_idx + len(field_marker) : end_idx].strip()
            result[field] = field_content
        else:
            # 没有找到结束标记，尝试提取到下一个字段标记或末尾
            next_marker_pos = -1
            # 查找下一个字段标记（任何字段）
            for other_field in fields:
                if other_field == field:
                    continue
                marker = f"【{other_field}】"
                pos = content.find(marker, start_idx + len(field_marker))
                if pos != -1 and (next_marker_pos == -1 or pos < next_marker_pos):
                    next_marker_pos = pos

            if next_marker_pos != -1:
                # 提取到下一个字段标记之前的内容
                field_content = content[start_idx + len(field_marker) : next_marker_pos].strip()
                result[field] = field_content
            else:
                # 提取到末尾
                field_content = content[start_idx + len(field_marker) :].strip()
                result[field] = field_content

    return result


class AiService:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-reasoner",
        global_config: dict[str, Any] | None = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.global_config = global_config or {}
        self.model = self.global_config.get("default_model") or model

    def _log_request(self, method: str, params: dict[str, Any]):
        logger.info(f"=== API 请求: {method} ===")
        logger.info(f"Model: {params.get('model')}")
        logger.info(f"Temperature: {params.get('temperature')}")
        logger.info(f"Top_p: {params.get('top_p')}")
        logger.info(f"Max_tokens: {params.get('max_tokens')}")
        logger.info(f"Stream: {params.get('stream')}")
        for i, msg in enumerate(params.get("messages", [])):
            content = msg.get("content", "")
            logger.info(f"Message[{i}] ({msg.get('role')}): {content}")

    def _log_response(self, response: Any):
        logger.info("=== API 响应 ===")
        logger.info(f"Model: {response.model}")
        logger.info(f"Usage: {response.usage}")
        content = response.choices[0].message.content
        logger.info(f"Content: {content}")

    def _get_temperature_and_tokens(self, book: Book | None = None) -> tuple[float, int]:
        """获取温度和最大 token 数"""
        temperature = DEFAULT_TEMPERATURE
        max_tokens = DEFAULT_MAX_TOKENS
        if book:
            temperature = _get_config_value(book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
            max_tokens = _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)
        elif self.global_config:
            temp_value = self.global_config.get("temperature")
            tokens_value = self.global_config.get("max_tokens")
            if temp_value is not None:
                temperature = float(str(temp_value))
            if tokens_value is not None:
                max_tokens = int(str(tokens_value))
        return temperature, max_tokens

    def _get_temperature_top_p_tokens(self, book: Book) -> tuple[float, float, int]:
        """获取温度、top_p 和最大 token 数"""
        temperature = _get_config_value(book, self.global_config, "temperature", DEFAULT_TEMPERATURE)
        top_p = _get_config_value(book, self.global_config, "top_p", DEFAULT_TOP_P)
        max_tokens = _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS)
        return temperature, top_p, max_tokens

    # Agent 方法已迁移到 app/services/agents/ 目录下
    # 使用 InitBookAgent, ChapterWriterAgent, SummaryAgent
