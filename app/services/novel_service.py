import json
import logging
import re
from collections.abc import AsyncGenerator

from app.repositories.file_repository import FileRepository, Book, Chapter
from app.services.ai_service import AiService
from app.services.agents import ChapterWriterAgent, SummaryAgent
from app.utils.ai_utils import get_agent_prompt, extract_stable_sections, extract_dynamic_sections
from app.constants import DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class NovelService:
    def __init__(self, repo: FileRepository, ai_service: AiService):
        self.repo = repo
        self.ai_service = ai_service

    def get_book(self, book_id: int) -> Book | None:
        return self.repo.get_book(book_id)

    def get_chapter(self, book_id: int, chapter_number: int) -> Chapter | None:
        return self.repo.get_chapter(book_id, chapter_number)

    def get_chapters(self, book_id: int) -> list[Chapter]:
        return self.repo.get_chapters(book_id)

    def get_prev_ending(self, book_id: int, chapter_number: int, chars: int = 600) -> str:
        return self.repo.get_prev_ending(book_id, chapter_number, chars)

    def get_max_chapter_number(self, book_id: int) -> int:
        return self.repo.get_max_chapter_number(book_id)

    async def write_chapter(self, book: Book, chapter_number: int, core_event: str, prev_ending: str) -> str:
        agent = ChapterWriterAgent(self.ai_service, book, self.ai_service.global_config)
        return await agent.write(chapter_number, core_event, prev_ending)

    async def stream_write_chapter(
        self, book: Book, chapter_number: int, core_event: str, prev_ending: str
    ) -> AsyncGenerator[str]:
        agent = ChapterWriterAgent(self.ai_service, book, self.ai_service.global_config)
        async for chunk in agent.write_stream(chapter_number, core_event, prev_ending):
            yield chunk

    async def update_summary(self, book: Book, chapter_number: int | None = None) -> str:
        if chapter_number is None:
            chapter_number = int(book.current_chapter) if book.current_chapter else 1

        chapter = self.repo.get_chapter(book.id, chapter_number)
        if not chapter:
            raise ValueError("章节不存在")

        chapter_title = str(chapter.title) if chapter.title else f"第{chapter_number}章"

        if chapter.content:
            new_chapter_text = chapter.content
        elif chapter.core_event:
            new_chapter_text = f"[本章内容尚未生成，仅有核心事件规划]\n核心事件：{chapter.core_event}"
        else:
            raise ValueError("章节内容和核心事件都为空，无法更新摘要")

        max_chapter = self.repo.get_max_chapter_number(book.id)
        is_last_chapter = chapter_number >= max_chapter

        agent = SummaryAgent(self.ai_service, book, self.ai_service.global_config)
        return await agent.update(new_chapter_text, chapter_number, is_last_chapter, chapter_title)

    async def stream_update_summary(self, book: Book, chapter_number: int | None = None) -> AsyncGenerator[str]:
        if chapter_number is None:
            chapter_number = int(book.current_chapter) if book.current_chapter else 1

        chapter = self.repo.get_chapter(book.id, chapter_number)
        if not chapter:
            raise ValueError("章节不存在")

        chapter_title = str(chapter.title) if chapter.title else f"第{chapter_number}章"

        if chapter.content:
            new_chapter_text = chapter.content
        elif chapter.core_event:
            new_chapter_text = f"[本章内容尚未生成，仅有核心事件规划]\n核心事件：{chapter.core_event}"
        else:
            raise ValueError("章节内容和核心事件都为空，无法更新摘要")

        max_chapter = self.repo.get_max_chapter_number(book.id)
        is_last_chapter = chapter_number >= max_chapter

        agent = SummaryAgent(self.ai_service, book, self.ai_service.global_config)
        async for chunk in agent.update_stream(new_chapter_text, chapter_number, is_last_chapter, chapter_title):
            yield chunk

    def update_chapter_title_and_core_event(self, book: Book, chapter_number: int, title: str, core_event: str):
        chapter = self.repo.get_chapter(book.id, chapter_number)
        if chapter:
            self.repo.update_chapter(chapter, title=title)
            chapter.core_event = core_event
            self.repo.update_chapter(chapter)

    def save_summary(self, book: Book, summary: str) -> Book:
        book.memory_summary = summary
        return self.repo.update_book(book)

    def update_style(self, book: Book, style: str) -> Book:
        book.style = style
        return self.repo.update_book(book)

    def save_chapter(
        self, book: Book, chapter_number: int, content: str, title: str | None = None
    ) -> tuple[Chapter, bool]:
        chapter = self.repo.get_chapter(book.id, chapter_number)
        is_new = chapter is None

        if is_new:
            title = title or self._extract_title(content) or f"第{chapter_number}章"
            chapter = self.repo.create_chapter(
                book_id=book.id, chapter_number=chapter_number, title=title, content=content, status="已完成"
            )
        else:
            existing_title = str(chapter.title) if chapter.title else None
            title = title or existing_title or self._extract_title(content) or f"第{chapter_number}章"
            chapter = self.repo.update_chapter(chapter, title=title, content=content, status="已完成")

        book.current_chapter = chapter_number
        self.repo.update_book(book)

        return chapter, is_new

    def _extract_title(self, content: str) -> str | None:
        match = re.search(r"^#\s*(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        lines = content.split("\n")
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 5 and len(line) < 100:
                return line
        return None

    async def optimize_outline(
        self, book: Book, chapter_position: int, user_title: str, user_core_event: str
    ) -> dict[str, str]:
        prompt_template = get_agent_prompt(self.ai_service.global_config, "optimize_outline_user_prompt", book)
        style = getattr(book, "style", "") or ""
        memory_summary = getattr(book, "memory_summary", "") or ""
        stable = extract_stable_sections(memory_summary)
        characters = ""
        world_view = ""
        if stable:
            c_match = re.search(r"【人物卡】\s*(.*?)(?=\n【|$)", stable, re.DOTALL)
            if c_match:
                characters = c_match.group(1).strip()
            w_match = re.search(r"【世界观】\s*(.*?)(?=\n【|$)", stable, re.DOTALL)
            if w_match:
                world_view = w_match.group(1).strip()
        dynamic = extract_dynamic_sections(memory_summary)
        progress = ""
        foreshadowing = ""
        if dynamic:
            p_match = re.search(r"【主线进度】\s*(.*?)(?=\n【|$)", dynamic, re.DOTALL)
            if p_match:
                progress = p_match.group(1).strip()
            f_match = re.search(r"【伏笔清单】\s*(.*?)(?=\n【|$)", dynamic, re.DOTALL)
            if f_match:
                foreshadowing = f_match.group(1).strip()
        prompt = prompt_template.format(
            chapter_position=chapter_position,
            style=style or "无",
            characters=characters or "无",
            world_view=world_view or "无",
            progress=progress or "无",
            foreshadowing=foreshadowing or "无",
            user_title=user_title,
            user_core_event=user_core_event,
        )
        agent_models = self.ai_service.global_config.get("agent_models", {}) or {}
        model = agent_models.get("chapter_writer") or "deepseek-v4-flash"
        result = await self.ai_service.call_llm(
            user_prompt=prompt,
            system_prompt="你是一个专业的小说创作辅助AI，帮助作者优化章节提纲。",
            response_format={"type": "json_object"},
            model=model,
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        try:
            return json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            return {"title": user_title, "core_event": user_core_event}

    def finish_book(self, book: Book) -> Book:
        book.status = "已完结"
        return self.repo.update_book(book)

    def add_chapter(self, book: Book, position: int, title: str, core_event: str = "") -> Chapter:
        max_num = self.repo.get_max_chapter_number(book.id)
        if position < 1:
            position = 1
        if position > max_num + 1:
            position = max_num + 1
        chapter = self.repo.insert_chapter_at(book.id, position, title, core_event)
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        if position <= current:
            book.current_chapter = current + 1
            self.repo.update_book(book)
        new_max = max(max_num + 1, position)
        book.target_chapters = new_max
        self.repo.update_book(book)
        return chapter

    def delete_chapter(self, book: Book, chapter_number: int) -> bool:
        chapter = self.repo.get_chapter(book.id, chapter_number)
        if not chapter:
            return False
        self.repo.delete_chapter(chapter)
        max_num = self.repo.get_max_chapter_number(book.id)
        if chapter_number <= max_num:
            self.repo.renumber_chapters(book.id, chapter_number + 1, offset=-1)
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        if chapter_number <= current:
            book.current_chapter = max(0, current - 1)
            self.repo.update_book(book)
        new_max = self.repo.get_max_chapter_number(book.id)
        book.target_chapters = new_max
        self.repo.update_book(book)
        return True

    def delete_book(self, book: Book):
        from app.services.file_service import delete_book_files

        self.repo.delete_book(book.id)
        delete_book_files(book.id)

    def get_book_export_content(self, book: Book) -> str:
        chapters = self.repo.get_chapters(book.id)
        lines = [f"《{book.title}》\n\n"]
        for ch in chapters:
            lines.append(f"第{ch.chapter_number}章 {ch.title}\n\n")
            lines.append(str(ch.content or ""))
            lines.append("\n\n")
        return "".join(lines)
