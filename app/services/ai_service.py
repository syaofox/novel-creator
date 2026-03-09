import json
import logging
from typing import Any, cast
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from app.utils import prompts
from app.models import Book

logger = logging.getLogger(__name__)


class AiService:
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1", model: str = "deepseek-reasoner"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _log_request(self, method: str, params: dict[str, Any]):
        logger.info(f"=== API 请求: {method} ===")
        logger.info(f"Model: {params.get('model')}")
        logger.info(f"Temperature: {params.get('temperature')}")
        logger.info(f"Top_p: {params.get('top_p')}")
        logger.info(f"Max_tokens: {params.get('max_tokens')}")
        logger.info(f"Stream: {params.get('stream')}")
        for i, msg in enumerate(params.get("messages", [])):
            content = msg.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            logger.info(f"Message[{i}] ({msg.get('role')}): {content}")

    def _log_response(self, response: Any):
        logger.info("=== API 响应 ===")
        logger.info(f"Model: {response.model}")
        logger.info(f"Usage: {response.usage}")
        content = response.choices[0].message.content
        if content and len(content) > 200:
            logger.info(f"Content: {content[:200]}...")
        else:
            logger.info(f"Content: {content}")

    async def initialize_book(self, basic_idea: str, genre: str, target_chapters: int) -> dict[str, str]:
        """调用初始化 Prompt，返回解析后的数据"""
        user_prompt = prompts.INIT_PROMPT.format(basic_idea=basic_idea, genre=genre, target_chapters=target_chapters)
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "你是一个专业的小说创作辅助AI，请严格按照要求输出JSON格式。"},
            {"role": "user", "content": user_prompt},
        ]
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
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

    async def write_chapter(self, book: Book, chapter_number: int, core_event: str, prev_ending: str) -> str:
        """生成下一章正文"""
        system_prompt = (
            book.config["jailbreak_prefix"]
            + "\n\n"
            + book.config["system_template"].format(memory=book.memory_summary, style="请根据小说的风格规范进行写作。")
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
            "temperature": book.config.get("temperature", 0.78),
            "top_p": book.config.get("top_p", 0.92),
            "max_tokens": book.config.get("max_tokens", 8192),
            "stream": book.config.get("stream", True),
        }
        self._log_request("write_chapter", params)
        response = await self.client.chat.completions.create(**params)
        self._log_response(response)
        return response.choices[0].message.content or ""

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
