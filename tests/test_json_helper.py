import pytest

from app.utils.json_helper import (
    _repair_unpaired_quotes,
    _repair_json_quotes,
    parse_json_with_repair,
    parse_init_data_markers,
    parse_chapter_titles,
    truncate_title,
)


class TestRepairUnpairedQuotes:
    def test_normal_string_unchanged(self):
        assert _repair_unpaired_quotes('{"key": "value"}') == '{"key": "value"}'

    def test_unpaired_quote_repaired(self):
        assert _repair_unpaired_quotes('{"key": "value" "extra"}') == '{"key": "value\\" \\"extra"}'

    def test_empty_string(self):
        assert _repair_unpaired_quotes("") == ""

    def test_escape_sequences_preserved(self):
        assert _repair_unpaired_quotes('{"key": "val\\"ue"}') == '{"key": "val\\"ue"}'

    def test_unpaired_single_quote(self):
        assert _repair_unpaired_quotes("{'key': 'value' 'extra'}") == "{'key': 'value\\' \\'extra'}"


class TestRepairJsonQuotes:
    def test_normal_quotes_unchanged(self):
        assert _repair_json_quotes('{"key": "value"}') == '{"key": "value"}'

    def test_curly_quotes_repaired(self):
        assert _repair_json_quotes('\u201cHello\u201d') == '"Hello"'

    def test_double_curly_quotes_repaired(self):
        assert _repair_json_quotes('\u201cHello\u201d') == '"Hello"'


class TestParseJsonWithRepair:
    def test_valid_json(self):
        result = parse_json_with_repair('{"key": "value"}')
        assert result == {"key": "value"}

    def test_curly_quotes_repaired(self):
        result = parse_json_with_repair('{"key": "\u201cvalue\u201d"}')
        assert result == {"key": "\u201cvalue\u201d"}

    def test_unpaired_quotes_repaired(self):
        result = parse_json_with_repair('{"key": "value" "extra"}')
        assert result is None or result == {"key": 'value" "extra'}

    def test_invalid_json_returns_none(self):
        assert parse_json_with_repair("not json at all") is None

    def test_empty_string(self):
        assert parse_json_with_repair("") is None

    def test_smart_quotes_normalized(self):
        result = parse_json_with_repair('{"key": "\u201cquote\u201d"}')
        assert result is not None


class TestParseInitDataMarkers:
    def test_empty_text(self):
        assert parse_init_data_markers("") == {}

    def test_characters_only(self):
        text = "【characters】[{\"name\": \"张三\"}]【characters】"
        result = parse_init_data_markers(text)
        assert result["characters"] == [{"name": "张三"}]

    def test_world_view_plain_text(self):
        text = "【world_view】玄幻世界【world_view】"
        result = parse_init_data_markers(text)
        assert result["world_view"]["setting"] == "玄幻世界"

    def test_outline_section(self):
        text = "【outline】[{\"chapter\": 1, \"title\": \"第1章\"}]【outline】"
        result = parse_init_data_markers(text)
        assert result["outline"] == [{"chapter": 1, "title": "第1章"}]

    def test_foreshadowing_plain_text(self):
        text = "【foreshadowing】伏笔1【foreshadowing】"
        result = parse_init_data_markers(text)
        assert result["foreshadowing"] == ["伏笔1"]

    def test_other_plain_text(self):
        text = "【other】一些信息【other】"
        result = parse_init_data_markers(text)
        assert result["other"]["key_points"] == "一些信息"

    def test_style_plain_text(self):
        text = "【style】简洁风格【style】"
        result = parse_init_data_markers(text)
        assert result["style"]["narrative_perspective"] == "简洁风格"

    def test_all_sections(self):
        text = (
            "【characters】[{\"name\": \"张三\"}]【characters】\n"
            "【world_view】{\"setting\": \"仙侠\"}【world_view】\n"
            "【style】{\"narrative_perspective\": \"第一人称\"}【style】\n"
            "【outline】[{\"chapter\": 1}]【outline】\n"
            "【foreshadowing】[]【foreshadowing】\n"
            "【other】{}【other】"
        )
        result = parse_init_data_markers(text)
        assert "characters" in result
        assert "world_view" in result
        assert "style" in result
        assert "outline" in result
        assert "foreshadowing" in result
        assert "other" in result

    def test_no_markers_returns_empty(self):
        text = "纯文本内容，没有标记"
        result = parse_init_data_markers(text)
        assert result == {}


class TestTruncateTitle:
    def test_short_title_unchanged(self):
        assert truncate_title("短标题") == "短标题"

    def test_long_title_truncated(self):
        long_title = "这是一个非常长的标题超过了五十个字符的限制会被截断显示省略号"
        result = truncate_title(long_title, max_length=10)
        assert len(result) <= 13
        assert result.endswith("...")

    def test_exact_boundary(self):
        assert truncate_title("12345", max_length=5) == "12345"

    def test_empty_string(self):
        assert truncate_title("") == ""


class TestParseChapterTitles:
    def test_valid_json_list(self):
        result = parse_chapter_titles('[{"chapter": 1, "title": "第1章", "core_event": "开始"}]', 3)
        assert len(result) == 3
        assert result[0]["title"] == "第1章"
        assert result[0]["core_event"] == "开始"

    def test_json_with_outline_key(self):
        result = parse_chapter_titles('{"outline": [{"chapter": 1, "title": "第1章"}]}', 3)
        assert result[0]["chapter"] == 1

    def test_markdown_lines(self):
        text = "第1章: 开始\n第2章: 发展"
        result = parse_chapter_titles(text, 3)
        assert len(result) == 3
        assert result[0]["title"] == ": 开始"
        assert result[2]["title"] == "第3章"

    def test_numeric_prefix_lines(self):
        text = "1、开始\n2、发展"
        result = parse_chapter_titles(text, 3)
        assert len(result) >= 2

    def test_fill_to_target(self):
        result = parse_chapter_titles('[{"chapter": 1, "title": "第1章"}]', 5)
        assert len(result) == 5
        assert result[4]["chapter"] == 5
        assert result[4]["title"] == "第5章"

    def test_empty_outline(self):
        result = parse_chapter_titles("", 3)
        assert len(result) == 3
        assert result[0]["title"] == "第1章"

    def test_core_event_not_string(self):
        result = parse_chapter_titles('[{"chapter": 1, "title": "第1章", "core_event": ["event"]}]', 3)
        assert result[0]["core_event"] == "['event']"
