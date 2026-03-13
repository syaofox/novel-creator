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

    async def initialize_book(
        self, basic_idea: str, genre: str, target_chapters: int, jailbreak_prefix: str = "", book: Book | None = None
    ) -> dict[str, str]:
        """调用初始化 Prompt，返回解析后的数据"""
        user_prompt = prompts.INIT_PROMPT.format(basic_idea=basic_idea, genre=genre, target_chapters=target_chapters)
        system_content = (
            ((jailbreak_prefix + "\n\n") if jailbreak_prefix else "")
            + """你是一个专业的小说创作辅助AI，请严格按照要求输出JSON格式。
重要：JSON 必须是有效的 JSON 语法。确保：
1. 所有字符串值必须用双引号括起来（例如："value"），不要使用单引号或省略引号
2. 对象键必须用双引号括起来
3. 不要有尾随逗号
4. 确保所有中文字符在引号内"""
        )
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        temperature, max_tokens = self._get_temperature_and_tokens(book)

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        self._log_request("initialize_book", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        content = response.choices[0].message.content
        if content is None:
            return {"characters": "", "world_view": "", "style": "", "outline": "", "foreshadowing": "", "other": ""}
        try:
            # 尝试提取并解析 JSON
            json_str = _extract_json(content)
            data = json.loads(json_str)
            # 确保返回的字典包含所有必需字段
            result = cast(dict[str, str], data)
            # 确保字段存在，如果缺失则提供空值
            required_fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
            for field in required_fields:
                if field not in result:
                    result[field] = ""
            return result
        except json.JSONDecodeError:
            logger.warning(f"无法解析 API 返回的 JSON，尝试解析标记格式，原始内容：{content[:500]}...")
            # 尝试解析标记格式
            parsed = _parse_marked_content(content)
            # 检查是否有字段被成功解析
            if any(parsed.values()):
                # 确保所有字段都存在
                required_fields = ["characters", "world_view", "style", "outline", "foreshadowing", "other"]
                for field in required_fields:
                    if field not in parsed:
                        parsed[field] = ""
                return parsed
            # 如果标记解析也失败，返回原始内容作为 characters 字段
            return {
                "characters": content,
                "world_view": "",
                "style": "",
                "outline": "",
                "foreshadowing": "",
                "other": "",
            }

    async def stream_initialize_book(
        self,
        basic_idea: str,
        genre: str,
        target_chapters: int,
        jailbreak_prefix: str = "",
        style: str = "",
        book: Book | None = None,
    ):
        """流式初始化小说，直接返回原始内容块"""
        style_section = (
            f"\n\n【用户指定的风格规范】\n{style}\n\n请在生成人物卡和大纲时充分考虑用户的风格偏好。" if style else ""
        )
        system_content = (
            ((jailbreak_prefix + "\n\n") if jailbreak_prefix else "")
            + """你是一个专业的小说创作辅助AI。请严格按照以下格式输出，每个字段用【】标记包裹，中间是有效的JSON。

重要规则：
1. 只输出以下6个字段，顺序必须为：characters、world_view、style、outline、foreshadowing、other
2. 每个字段格式为：【字段名】<JSON内容>【字段名】，标记必须成对出现
3. JSON内容必须是有效的JSON，符合下方给出的结构
4. 不要添加任何额外文本、说明、解释或注释
5. 不要修改字段名，不要省略任何字段
6. outline数组必须包含恰好{target_chapters}个章节对象，chapter从1开始连续编号

字段格式示例：
【characters】
[
  {
    "name": "角色姓名",
    "nickname": "昵称",
    "age": 20,
    "appearance": "外貌描述",
    "personality": "性格特点",
    "background": "背景故事",
    "goal": "角色目标",
    "relationships": "人物关系"
  }
]
【characters】

请严格按照以下结构输出：

【characters】
[
  {
    "name": "角色姓名",
    "nickname": "昵称",
    "age": 20,
    "appearance": "外貌描述",
    "personality": "性格特点",
    "background": "背景故事",
    "goal": "角色目标",
    "relationships": "人物关系"
  }
]
【characters】

【world_view】
{
  "setting": "世界观设定",
  "special_rules": "特殊规则",
  "themes": "主题"
}
【world_view】

【style】
{
  "narrative_perspective": "叙事视角",
  "language_style": "语言风格",
  "pace": "节奏特点",
  "target_audience": "目标读者"
}
【style】

【outline】
[
  {"chapter": 1, "title": "章节标题", "core_event": "本章核心事件"}
]
【outline】

【foreshadowing】
["伏笔1", "伏笔2"]
【foreshadowing】

【other】
{
  "novel_title": "小说标题",
  "key_points": "关键要点",
   "writing_guidance": "写作指导"
}
【other】

重要：JSON 必须是有效的 JSON 语法。确保：
1. 所有字符串值必须用双引号括起来（例如："value"），不要使用单引号或省略引号
2. 对象键必须用双引号括起来
3. 不要有尾随逗号
4. 确保所有中文字符在引号内
"""
            + style_section
        )
        user_prompt = f"""用户创意：{basic_idea}
小说类型：{genre}
目标章节数：{target_chapters}"""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        temperature, max_tokens = self._get_temperature_and_tokens(book)

        params = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        self._log_request("stream_initialize_book", params)
        response = await self.client.chat.completions.create(**params, stream=True)
        first_chunk = True
        full_content = ""

        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式初始化） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_content += content
                yield {"content": content}

        logger.info(f"Stream completed, total content length: {len(full_content)}")
        logger.info(f"Full content: {full_content}")

    async def stream_write_chapter(self, book: Book, chapter_number: int, core_event: str, prev_ending: str):
        """流式生成下一章正文，异步生成内容块"""
        system_prompt = (
            _get_config_value(book, self.global_config, "jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
            + "\n\n"
            + _get_config_value(book, self.global_config, "system_template", DEFAULT_SYSTEM_TEMPLATE).format(
                memory=book.memory_summary, style=book.style or "请根据小说的风格规范进行写作。"
            )
        )
        user_prompt = prompts.WRITE_CHAPTER_PROMPT.format(
            chapter_number=chapter_number, core_event=core_event, prev_ending=prev_ending
        )
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        temperature, top_p, max_tokens = self._get_temperature_top_p_tokens(book)
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True,
        }
        self._log_request("stream_write_chapter", params)
        response = await self.client.chat.completions.create(**params)
        first_chunk = True
        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("Stream completed")

    async def write_chapter(self, book: Book, chapter_number: int, core_event: str, prev_ending: str) -> str:
        """非流式生成下一章正文，返回完整内容"""
        system_prompt = (
            _get_config_value(book, self.global_config, "jailbreak_prefix", DEFAULT_JAILBREAK_PREFIX)
            + "\n\n"
            + _get_config_value(book, self.global_config, "system_template", DEFAULT_SYSTEM_TEMPLATE).format(
                memory=book.memory_summary, style=book.style or "请根据小说的风格规范进行写作。"
            )
        )
        user_prompt = prompts.WRITE_CHAPTER_PROMPT.format(
            chapter_number=chapter_number, core_event=core_event, prev_ending=prev_ending
        )
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        temperature, top_p, max_tokens = self._get_temperature_top_p_tokens(book)
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        self._log_request("write_chapter", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def update_summary(self, book: Book, new_chapter_text: str, chapter_number: int | None = None) -> str:
        """根据新章节和旧摘要生成新摘要"""
        if chapter_number is None:
            chapter_number = int(book.current_chapter) if book.current_chapter else 1
        next_chapter = min(chapter_number + 1, book.target_chapters)
        user_prompt = prompts.UPDATE_SUMMARY_PROMPT.format(
            old_summary=book.memory_summary,
            new_chapter=new_chapter_text,
            chapter_number=chapter_number,
            next_chapter=next_chapter,
        )
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "你是一个小说摘要更新专家，请根据旧摘要和新章节生成更新后的摘要，保持6部分格式。重点关注伏笔回收和主线进度更新。",
            },
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": _get_config_value(book, self.global_config, "temperature", 0.5),
            "max_tokens": _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS),
        }
        self._log_request("update_summary", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def stream_update_summary(self, book: Book, new_chapter_text: str, chapter_number: int | None = None):
        """流式生成新摘要"""
        if chapter_number is None:
            chapter_number = int(book.current_chapter) if book.current_chapter else 1
        next_chapter = min(chapter_number + 1, book.target_chapters)
        user_prompt = prompts.UPDATE_SUMMARY_PROMPT.format(
            old_summary=book.memory_summary,
            new_chapter=new_chapter_text,
            chapter_number=chapter_number,
            next_chapter=next_chapter,
        )
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "你是一个小说摘要更新专家，请根据旧摘要和新章节生成更新后的摘要，保持6部分格式。重点关注伏笔回收和主线进度更新。",
            },
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": _get_config_value(book, self.global_config, "temperature", 0.5),
            "max_tokens": _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS),
            "stream": True,
        }
        self._log_request("stream_update_summary", params)
        response = await self.client.chat.completions.create(**params)
        first_chunk = True
        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式摘要） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("Stream summary completed")

    async def stream_compress_summary(self, book: Book):
        """流式压缩摘要"""
        user_prompt = prompts.COMPRESS_SUMMARY_PROMPT.format(summary=book.memory_summary)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "你是一个摘要压缩专家，请将以下小说摘要压缩至2500字以内，保留6部分格式。"},
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": _get_config_value(book, self.global_config, "temperature", 0.5),
            "max_tokens": _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS),
            "stream": True,
        }
        self._log_request("stream_compress_summary", params)
        response = await self.client.chat.completions.create(**params)
        first_chunk = True
        async for chunk in response:
            if first_chunk:
                logger.info("=== API 响应（流式压缩摘要） ===")
                logger.info(f"Model: {chunk.model}")
                first_chunk = False
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        logger.info("Stream compress summary completed")

    async def compress_summary(self, book: Book) -> str:
        """压缩摘要（保留6部分格式）"""
        user_prompt = prompts.COMPRESS_SUMMARY_PROMPT.format(summary=book.memory_summary)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "你是一个摘要压缩专家，请将以下小说摘要压缩至2500字以内，保留6部分格式。"},
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": _get_config_value(book, self.global_config, "temperature", 0.5),
            "max_tokens": _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS),
        }
        self._log_request("compress_summary", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""
