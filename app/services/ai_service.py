import json
import logging
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
    book_config = dict(book.config) if book.config is not None else {}
    if key in book_config:
        return book_config[key]
    if global_config is not None and key in global_config:
        value = global_config[key]
        if key in ("temperature", "top_p"):
            return float(value) if value else default
        if key == "max_tokens":
            return int(value) if value else default
        if key == "stream":
            return bool(int(value)) if value else default
        return value
    return default


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

    async def initialize_book(
        self, basic_idea: str, genre: str, target_chapters: int, jailbreak_prefix: str = ""
    ) -> dict[str, str]:
        """调用初始化 Prompt，返回解析后的数据"""
        user_prompt = prompts.INIT_PROMPT.format(basic_idea=basic_idea, genre=genre, target_chapters=target_chapters)
        system_content = (
            (jailbreak_prefix + "\n\n") if jailbreak_prefix else ""
        ) + "你是一个专业的小说创作辅助AI，请严格按照要求输出JSON格式。"
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": DEFAULT_TEMPERATURE,
            "response_format": {"type": "json_object"},
        }
        self._log_request("initialize_book", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        content = response.choices[0].message.content
        if content is None:
            return {"characters": "", "world_view": "", "style": "", "outline": "", "foreshadowing": "", "other": ""}
        try:
            data = json.loads(content)
            return cast(dict[str, str], data)
        except json.JSONDecodeError:
            return {
                "characters": content,
                "world_view": "",
                "style": "",
                "outline": "",
                "foreshadowing": "",
                "other": "",
            }

    async def stream_initialize_book(
        self, basic_idea: str, genre: str, target_chapters: int, jailbreak_prefix: str = ""
    ):
        """流式初始化小说，直接返回原始内容块"""
        user_prompt = prompts.INIT_PROMPT.format(basic_idea=basic_idea, genre=genre, target_chapters=target_chapters)
        system_content = (
            ((jailbreak_prefix + "\n\n") if jailbreak_prefix else "")
            + "你是一个专业的小说创作辅助AI。请严格按照以下JSON格式输出，每个字段用【】标记包裹：\n"
            + "【characters】人物卡内容【characters】\n"
            + "【world_view】世界观内容【world_view】\n"
            + "【style】风格规范内容【style】\n"
            + "【outline】大纲内容（JSON数组）【outline】\n"
            + "【foreshadowing】伏笔内容【foreshadowing】\n"
            + "【other】其他信息内容【other】"
        )
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }
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
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": _get_config_value(book, self.global_config, "temperature", DEFAULT_TEMPERATURE),
            "top_p": _get_config_value(book, self.global_config, "top_p", DEFAULT_TOP_P),
            "max_tokens": _get_config_value(book, self.global_config, "max_tokens", DEFAULT_MAX_TOKENS),
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

    async def update_summary(self, book: Book, new_chapter_text: str) -> str:
        """根据新章节和旧摘要生成新摘要"""
        user_prompt = prompts.UPDATE_SUMMARY_PROMPT.format(
            old_summary=book.memory_summary, new_chapter=new_chapter_text
        )
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "你是一个小说摘要生成专家，请根据旧摘要和新章节生成更新后的摘要，保持6部分格式。",
            },
            {"role": "user", "content": user_prompt},
        ]
        params = {"model": self.model, "messages": messages, "temperature": 0.5, "max_tokens": 2000}
        self._log_request("update_summary", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def global_review(self, book: Book) -> str:
        """全局回顾，返回格式化检查结果"""
        user_prompt = prompts.REVIEW_PROMPT.format(memory_summary=book.memory_summary)
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "你是一个专业的小说编辑，请对以下小说摘要进行全面回顾，检查人设、主线、伏笔、逻辑等问题，并给出建议。",
            },
            {"role": "user", "content": user_prompt},
        ]
        params = {"model": self.model, "messages": messages, "temperature": 0.7, "max_tokens": 2000}
        self._log_request("global_review", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

    async def compress_summary(self, book: Book) -> str:
        """压缩摘要（保留6部分格式）"""
        user_prompt = prompts.COMPRESS_SUMMARY_PROMPT.format(summary=book.memory_summary)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "你是一个摘要压缩专家，请将以下小说摘要压缩至2500字以内，保留6部分格式。"},
            {"role": "user", "content": user_prompt},
        ]
        params = {"model": self.model, "messages": messages, "temperature": 0.5, "max_tokens": 1500}
        self._log_request("compress_summary", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""
