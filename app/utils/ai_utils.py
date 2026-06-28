import json
import logging
import re
from typing import Any

from app.repositories.file_repository import Book
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
)
from app.utils import prompts

logger = logging.getLogger(__name__)

PROMPT_DEFAULTS: dict[str, str] = {
    "system_template": DEFAULT_SYSTEM_TEMPLATE,
    "jailbreak_prefix": DEFAULT_JAILBREAK_PREFIX,
    "chapter_writer_user_prompt": prompts.WRITE_CHAPTER_PROMPT,
    "summary_system_prompt": prompts.UPDATE_SUMMARY_SYSTEM_PROMPT,
    "summary_user_prompt": prompts.UPDATE_SUMMARY_PROMPT,
    "summary_user_prompt_last": prompts.UPDATE_SUMMARY_PROMPT_LAST,
    "init_book_system_prompt": prompts.INIT_BOOK_SYSTEM_PROMPT,
    "init_book_user_prompt": "用户创意：{basic_idea}\n小说类型：{genre}\n目标章节数：{target_chapters}",
    "style_extractor_system_prompt": (
        "你是一个专业的小说写作风格分析专家。"
        "请分析给定的文字片段，提取其写作风格特征，"
        "包括但不限于：句式特点、修辞手法、节奏韵律、"
        "用词偏好、叙事视角、情感基调、场景描写方式等。"
    ),
    "style_extractor_user_prompt": (
        "请以 JSON 格式分析以下文字片段的写作风格。\n"
        "要求：\n"
        '- "title"：为这种风格取一个简洁准确的名称（2-6个字）\n'
        '- "content"：详细描述该风格的各个特征，每一条独立成行\n'
        '示例：{"title": "简洁干练", "content": "1. 短句为主，节奏明快\\n2. 多用白描手法\\n3. 叙事直白精炼"}'
    ),
    "optimize_outline_user_prompt": prompts.OPTIMIZE_OUTLINE_PROMPT,
}


def get_agent_prompt(global_config: dict[str, Any] | None, key: str, book: Book | None = None) -> str:
    """获取 Agent prompt，按 book.config → global_config.agent_prompts → PROMPT_DEFAULTS 优先级解析"""
    if book:
        book_config = book.config if book.config is not None else {}
        if key in book_config and book_config[key]:
            return book_config[key]

    agent_prompts = (global_config or {}).get("agent_prompts", {}) if global_config else {}
    value = agent_prompts.get(key)
    if value:
        return value

    return PROMPT_DEFAULTS.get(key, "")


def get_config_value(book: Book | None, global_config: dict[str, Any] | None, key: str, default: Any) -> Any:
    """获取配置值：优先使用书籍配置，其次使用全局配置，最后使用默认值"""
    if book:
        book_config = book.config if book.config is not None else {}
        if key in book_config:
            return book_config[key]

    if global_config is not None and key in global_config:
        return global_config[key]

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


MEMORY_STABLE_SECTIONS = ["人物卡", "世界观", "风格规范"]
MEMORY_DYNAMIC_SECTIONS = ["主线进度", "伏笔清单", "其他信息"]


def extract_stable_sections(memory_summary: str) -> str:
    """从记忆摘要中提取稳定的章节(人物卡,世界观,风格规范)

    这些 sections 变化频率低,可以注入 system prompt 以提高 DeepSeek V4 缓存命中率。
    """
    if not memory_summary:
        return ""
    sections = []
    for key in MEMORY_STABLE_SECTIONS:
        pattern = rf"【{key}】\s*(.*?)(?=\n【|$)"
        match = re.search(pattern, memory_summary, re.DOTALL)
        if match:
            content = match.group(1).strip()
            if content:
                sections.append(f"【{key}】\n{content}")
    return "\n\n".join(sections)


def extract_dynamic_sections(memory_summary: str) -> str:
    """从记忆摘要中提取动态章节(主线进度,伏笔清单,其他信息)

    这些 sections 每章都会变化,应放在 user prompt 中。
    """
    if not memory_summary:
        return ""
    sections = []
    for key in MEMORY_DYNAMIC_SECTIONS:
        pattern = rf"【{key}】\s*(.*?)(?=\n【|$)"
        match = re.search(pattern, memory_summary, re.DOTALL)
        if match:
            content = match.group(1).strip()
            if content:
                sections.append(f"【{key}】\n{content}")
    return "\n\n".join(sections)


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
