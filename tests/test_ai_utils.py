import pytest
from unittest.mock import MagicMock

from app.utils.ai_utils import (
    get_agent_prompt,
    get_config_value,
    get_temperature_top_p_tokens,
    extract_json,
    extract_stable_sections,
    extract_dynamic_sections,
    parse_marked_content,
)


class TestGetAgentPrompt:
    def test_book_config_takes_priority(self):
        book = MagicMock()
        book.config = {"test_key": "from_book"}
        result = get_agent_prompt({}, "test_key", book)
        assert result == "from_book"

    def test_global_config_second_priority(self):
        book = MagicMock()
        book.config = {}
        result = get_agent_prompt({"agent_prompts": {"test_key": "from_global"}}, "test_key", book)
        assert result == "from_global"

    def test_default_fallback(self):
        result = get_agent_prompt({}, "nonexistent_key")
        assert result == ""

    def test_book_config_empty_uses_global(self):
        book = MagicMock()
        book.config = {"other_key": "val"}
        result = get_agent_prompt(
            {"agent_prompts": {"test_key": "from_global"}}, "test_key", book
        )
        assert result == "from_global"

    def test_none_global_config(self):
        book = MagicMock()
        book.config = {}
        result = get_agent_prompt(None, "test_key", book)
        assert result == ""

    def test_default_prompt_values_exist(self):
        from app.utils.ai_utils import PROMPT_DEFAULTS
        assert "chapter_writer_user_prompt" in PROMPT_DEFAULTS
        assert "summary_system_prompt" in PROMPT_DEFAULTS


class TestGetConfigValue:
    def test_book_config_priority(self):
        book = MagicMock()
        book.config = {"key": "book_val"}
        result = get_config_value(book, {"key": "global_val"}, "key", "default")
        assert result == "book_val"

    def test_global_config_second(self):
        result = get_config_value(None, {"key": "global_val"}, "key", "default")
        assert result == "global_val"

    def test_default_last(self):
        result = get_config_value(None, {}, "key", "default_val")
        assert result == "default_val"

    def test_book_config_empty_dict(self):
        book = MagicMock()
        book.config = {}
        result = get_config_value(book, {"key": "global_val"}, "key", "default")
        assert result == "global_val"


class TestGetTemperatureTopP:
    def test_defaults(self):
        temp, top_p, max_tokens = get_temperature_top_p_tokens(None, {})
        from app.constants import DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS
        assert temp == DEFAULT_TEMPERATURE
        assert top_p == DEFAULT_TOP_P
        assert max_tokens == DEFAULT_MAX_TOKENS

    def test_book_overrides(self):
        book = MagicMock()
        book.config = {"temperature": 0.5, "top_p": 0.8, "max_tokens": 8192}
        temp, top_p, max_tokens = get_temperature_top_p_tokens(book, {})
        assert temp == 0.5
        assert top_p == 0.8
        assert max_tokens == 8192


class TestExtractJson:
    def test_valid_json_direct(self):
        assert extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_json_block_extraction(self):
        text = "前置内容\n```json\n{\"key\": \"value\"}\n```\n后置内容"
        result = extract_json(text)
        assert result == '{"key": "value"}'

    def test_first_valid_json_block(self):
        text = "```json\n{\"first\": true}\n```\n```json\n{\"second\": true}\n```"
        result = extract_json(text)
        assert result == '{"first": true}'

    def test_brace_extraction(self):
        text = "前置内容{\"key\": \"value\"}后置内容"
        result = extract_json(text)
        assert result == '{"key": "value"}'

    def test_no_json_returns_original(self):
        result = extract_json("纯文本内容")
        assert result == "纯文本内容"

    def test_empty_string(self):
        assert extract_json("") == ""


class TestExtractSections:
    def test_extract_stable_sections(self):
        summary = "【人物卡】\n张三: 主角\n【世界观】\n仙侠世界"
        result = extract_stable_sections(summary)
        assert "人物卡" in result
        assert "世界观" in result
        assert "张三" in result

    def test_extract_stable_sections_empty(self):
        assert extract_stable_sections("") == ""

    def test_extract_dynamic_sections(self):
        summary = "【主线进度】\n第1章: 开始\n【伏笔清单】\n伏笔1"
        result = extract_dynamic_sections(summary)
        assert "主线进度" in result
        assert "伏笔清单" in result

    def test_extract_dynamic_sections_empty(self):
        assert extract_dynamic_sections("") == ""

    def test_both_extract_different_content(self):
        summary = "【人物卡】\n张三\n【主线进度】\n第1章: 开始"
        stable = extract_stable_sections(summary)
        dynamic = extract_dynamic_sections(summary)
        assert "人物卡" in stable
        assert "主线进度" in dynamic
        assert "人物卡" not in dynamic
        assert "主线进度" not in stable

    def test_empty_sections_not_included(self):
        summary = "【人物卡】\n\n【世界观】\n仙侠世界"
        result = extract_stable_sections(summary)
        assert "人物卡" in result
        assert "世界观" in result


class TestParseMarkedContent:
    def test_parse_all_fields(self):
        content = (
            "【characters】张三【characters】\n"
            "【world_view】仙侠世界【world_view】\n"
            "【style】简洁【style】\n"
            "【outline】第1章:开始【outline】\n"
            "【foreshadowing】伏笔1【foreshadowing】\n"
            "【other】其他【other】"
        )
        result = parse_marked_content(content)
        assert result["characters"] == "张三"
        assert result["world_view"] == "仙侠世界"
        assert result["style"] == "简洁"
        assert result["other"] == "其他"

    def test_missing_field_returns_empty(self):
        result = parse_marked_content("【characters】张三【characters】")
        assert result["world_view"] == ""

    def test_unclosed_marker(self):
        content = "【characters】张三\n【world_view】仙侠世界【world_view】"
        result = parse_marked_content(content)
        assert result["characters"] == "张三"
        assert result["world_view"] == "仙侠世界"

    def test_markers_with_prefix(self):
        content = "[Pasted ~24 【characters】张三【characters】"
        result = parse_marked_content(content)
        assert result["characters"] == "张三"
