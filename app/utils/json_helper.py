import json
import re
from typing import Any


def _repair_unpaired_quotes(text: str) -> str:
    """修复 JSON 字符串内部未配对的引号"""
    result = ""
    in_string = False
    string_char = ""
    i = 0

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if not in_string:
            if char in ('"', "'"):
                in_string = True
                string_char = char
                result += char
            else:
                result += char
        else:
            if char == "\\" and next_char in ('"', "'"):
                result += char + next_char
                i += 2
                continue
            if char == string_char:
                rest = text[i + 1 :].strip()
                if (
                    rest == ""
                    or rest.startswith(",")
                    or rest.startswith("}")
                    or rest.startswith("]")
                    or rest.startswith(":")
                ):
                    in_string = False
                    result += char
                else:
                    result += "\\" + char
            else:
                result += char
        i += 1
    return result


def _repair_json_quotes(json_str: str) -> str:
    """修复 JSON 字符串中的引号问题"""
    repaired = json_str
    repaired = re.sub(r'[""]', '"', repaired)
    repaired = re.sub(r"[\u201C\u201D]", '"', repaired)
    return repaired


def parse_json_with_repair(text: str) -> Any | None:
    """尝试解析 JSON，失败则尝试修复后重试"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = text
        repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
        repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            repaired = _repair_unpaired_quotes(repaired)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                return None


def parse_init_data_markers(text: str) -> dict[str, Any]:
    """解析【】标记格式的初始化数据"""
    result: dict[str, Any] = {}

    def extract_section(key: str) -> str:
        pattern = rf"【{key}】([\s\S]*?)【{key}】"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return ""

    chars_text = extract_section("characters")
    if chars_text:
        parsed = parse_json_with_repair(chars_text)
        result["characters"] = parsed if parsed is not None else []

    wv_text = extract_section("world_view")
    if wv_text:
        parsed = parse_json_with_repair(wv_text)
        if parsed:
            result["world_view"] = parsed
        else:
            result["world_view"] = {"setting": wv_text, "special_rules": "", "themes": ""}

    style_text = extract_section("style")
    if style_text:
        parsed = parse_json_with_repair(style_text)
        if parsed:
            result["style"] = parsed
        else:
            result["style"] = {
                "narrative_perspective": style_text,
                "language_style": "",
                "pace": "",
                "target_audience": "",
            }

    outline_text = extract_section("outline")
    if outline_text:
        parsed = parse_json_with_repair(outline_text)
        result["outline"] = parsed if parsed is not None else []

    foreshadow_text = extract_section("foreshadowing")
    if foreshadow_text:
        parsed = parse_json_with_repair(foreshadow_text)
        if parsed:
            result["foreshadowing"] = parsed
        else:
            result["foreshadowing"] = [foreshadow_text]

    other_text = extract_section("other")
    if other_text:
        parsed = parse_json_with_repair(other_text)
        if parsed:
            result["other"] = parsed
        else:
            result["other"] = {"novel_title": "", "key_points": other_text, "writing_guidance": ""}

    return result


def truncate_title(title: str, max_length: int = 50) -> str:
    if len(title) > max_length:
        return title[:max_length].strip() + "..."
    return title


def parse_chapter_titles(outline: str, target_chapters: int) -> list[dict]:
    """从大纲中解析章节信息,返回 [{chapter, title, core_event}, ...]"""
    chapters = []

    try:
        data = json.loads(outline)
    except json.JSONDecodeError:
        try:
            data = json.loads(_repair_json_quotes(outline))
        except json.JSONDecodeError:
            lines = outline.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^(?:第\s*(\d+)\s*章|(\d+)[:、.]\s*)(.+)$", line)
                if match:
                    num = int(match.group(1) or match.group(2))
                    title = truncate_title(match.group(3).strip())
                    chapters.append({"chapter": num, "title": title, "core_event": ""})
                elif chapters or line:
                    chapters.append({"chapter": len(chapters) + 1, "title": truncate_title(line), "core_event": ""})
            while len(chapters) < target_chapters:
                chapters.append({"chapter": len(chapters) + 1, "title": f"第{len(chapters) + 1}章", "core_event": ""})
            return chapters[:target_chapters]

    if isinstance(data, dict) and "outline" in data:
        data = data["outline"]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                title = item.get("title", "")
                if not title:
                    title = f"第{len(chapters) + 1}章"
                title = truncate_title(title)
                core_event = item.get("core_event", "")
                if not isinstance(core_event, str):
                    core_event = str(core_event) if core_event else ""
                chapters.append(
                    {"chapter": item.get("chapter", len(chapters) + 1), "title": title, "core_event": core_event}
                )

    while len(chapters) < target_chapters:
        chapters.append({"chapter": len(chapters) + 1, "title": f"第{len(chapters) + 1}章", "core_event": ""})

    return chapters[:target_chapters]
