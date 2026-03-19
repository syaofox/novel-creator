import logging
import re
from typing import Any
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.models import Book, Chapter
from app.repositories.novel_repository import NovelRepository
from app.services.ai_service import AiService

logger = logging.getLogger(__name__)


class NovelService:
    def __init__(self, db: Session, ai_service: AiService):
        self.db = db
        self.ai_service = ai_service
        self.repo = NovelRepository(db)

    def get_book(self, book_id: int) -> Book | None:
        return self.repo.get_book_by_id(book_id)

    def get_chapter(self, book_id: int, chapter_number: int) -> Chapter | None:
        return self.repo.get_chapter(book_id, chapter_number)

    def get_chapters(self, book_id: int) -> list[Chapter]:
        return self.repo.get_chapters(book_id)

    def get_prev_ending(self, book_id: int, chapter_number: int, chars: int = 600) -> str:
        return self.repo.get_prev_ending(book_id, chapter_number, chars)

    async def write_chapter(self, book: Book, chapter_number: int, core_event: str, prev_ending: str) -> str:
        return await self.ai_service.write_chapter(book, chapter_number, core_event, prev_ending)

    async def stream_write_chapter(
        self, book: Book, chapter_number: int, core_event: str, prev_ending: str
    ) -> AsyncGenerator[str]:
        async for chunk in self.ai_service.stream_write_chapter(book, chapter_number, core_event, prev_ending):
            yield chunk

    async def update_summary(self, book: Book, chapter_number: int | None = None) -> str:
        """更新摘要，返回摘要文本"""
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

        return await self.ai_service.update_summary(
            book, new_chapter_text, chapter_number, is_last_chapter, chapter_title
        )

    async def stream_update_summary(self, book: Book, chapter_number: int | None = None) -> AsyncGenerator[str]:
        """流式更新摘要"""
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

        async for chunk in self.ai_service.stream_update_summary(
            book, new_chapter_text, chapter_number, is_last_chapter, chapter_title
        ):
            yield chunk

    def update_chapter_title_and_core_event(self, book: Book, chapter_number: int, title: str, core_event: str):
        """更新章节标题和核心事件"""
        chapter = self.repo.get_chapter(book.id, chapter_number)
        if chapter:
            self.repo.update_chapter(chapter, title=title)
            chapter.core_event = core_event
            self.repo.db.commit()

    async def compress_summary(self, book: Book) -> str:
        return await self.ai_service.compress_summary(book)

    async def stream_compress_summary(self, book: Book) -> AsyncGenerator[str]:
        async for chunk in self.ai_service.stream_compress_summary(book):
            yield chunk

    def save_summary(self, book: Book, summary: str) -> Book:
        return self.repo.update_book(book, memory_summary=summary)

    def update_style(self, book: Book, style: str) -> Book:
        return self.repo.update_book(book, style=style)

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

        self.repo.update_book(book, current_chapter=chapter_number)

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

    def finish_book(self, book: Book) -> Book:
        return self.repo.update_book(book, status="已完结")

    def add_chapter(self, book: Book, position: int, title: str, core_event: str = "") -> Chapter:
        """在指定位置添加新章节，后续章节自动重新编号"""
        max_num = self.repo.get_max_chapter_number(book.id)
        if position < 1:
            position = 1
        if position > max_num + 1:
            position = max_num + 1
        chapter = self.repo.insert_chapter_at(book.id, position, title, core_event)
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        if position <= current:
            self.repo.update_book(book, current_chapter=current + 1)
        # 更新 target_chapters 为实际最大章节数
        new_max = max(max_num + 1, position)
        self.repo.update_book(book, target_chapters=new_max)
        return chapter

    def delete_chapter(self, book: Book, chapter_number: int) -> bool:
        """删除指定章节，后续章节自动重新编号"""
        chapter = self.repo.get_chapter(book.id, chapter_number)
        if not chapter:
            return False
        self.repo.delete_chapter(chapter)
        max_num = self.repo.get_max_chapter_number(book.id)
        if chapter_number <= max_num:
            self.repo.renumber_chapters(book.id, chapter_number + 1, offset=-1)
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        if chapter_number <= current:
            new_current = max(0, current - 1)
            self.repo.update_book(book, current_chapter=new_current)
        # 更新 target_chapters 为实际最大章节数
        new_max = self.repo.get_max_chapter_number(book.id)
        self.repo.update_book(book, target_chapters=new_max)
        return True

    def get_max_chapter_number(self, book: Book) -> int:
        """获取书籍的最大章节号"""
        return self.repo.get_max_chapter_number(book.id)

    def delete_book(self, book: Book) -> None:
        from app.services.file_service import delete_book_files

        self.repo.delete_book(book)
        delete_book_files(book.id)

    def get_book_export_content(self, book: Book) -> str:
        chapters = self.repo.get_chapters(book.id)
        lines = [f"《{book.title}》\n\n"]
        for ch in chapters:
            lines.append(f"第{ch.chapter_number}章 {ch.title}\n\n")
            lines.append(str(ch.content or ""))
            lines.append("\n\n")
        return "".join(lines)
