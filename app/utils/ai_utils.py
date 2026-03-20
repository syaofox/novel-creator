import json
import logging
import re
from typing import Any

from app.models import Book
from app.constants import DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


def get_config_value(book: Book | None, global_config: dict[str, Any] | None, key: str, default: Any) -> Any:
    """获取配置值：优先使用书籍配置，其次使用全局配置，最后使用默认值"""
    if book:
        book_config = book.config if book.config is not None else {}
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


def get_temperature_top_p_tokens(book: Book | None, global_config: dict[str, Any] | None) -> tuple[float, float, int]:
    """获取温度、top_p 和最大 token 数"""
    temperature = get_config_value(book, global_config, "temperature", DEFAULT_TEMPERATURE)
    top_p = get_config_value(book, global_config, "top_p", DEFAULT_TOP_P)
    max_tokens = get_config_value(book, global_config, "max_tokens", DEFAULT_MAX_TOKENS)
    return temperature, top_p, max_tokens


def extract_json(content: str) -> str:
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


def parse_marked_content(content: str) -> dict[str, str]:
    """解析标记格式的内容，提取各个字段

    格式示例：
    【characters】...【characters】
    【world_view】...【world_view】
    也支持前缀如：[Pasted ~24 【characters】...
    """
    fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
    result = {}

    for field in fields:
        field_marker = f"【{field}】"
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
