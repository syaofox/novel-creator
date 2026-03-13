import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Book, Chapter
from app.models import get_china_now

logger = logging.getLogger(__name__)


class NovelRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_book_by_id(self, book_id: int) -> Book | None:
        return self.db.query(Book).filter(Book.id == book_id).first()

    def get_chapter(self, book_id: int, chapter_number: int) -> Chapter | None:
        return (
            self.db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_number).first()
        )

    def get_chapters(self, book_id: int) -> list[Chapter]:
        return self.db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()

    def get_latest_chapter(self, book_id: int) -> Chapter | None:
        return self.db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number.desc()).first()

    def create_chapter(
        self,
        book_id: int,
        chapter_number: int,
        title: str,
        content: str = "",
        core_event: str = "",
        status: str = "未完成",
    ) -> Chapter:
        chapter = Chapter(
            book_id=book_id,
            chapter_number=chapter_number,
            title=title,
            content=content,
            core_event=core_event,
            status=status,
        )
        self.db.add(chapter)
        self.db.commit()
        self.db.refresh(chapter)
        return chapter

    def update_chapter(
        self, chapter: Chapter, title: str | None = None, content: str | None = None, status: str | None = None
    ) -> Chapter:
        if title is not None:
            chapter.title = title
        if content is not None:
            chapter.content = content
        if status is not None:
            chapter.status = status
        self.db.commit()
        self.db.refresh(chapter)
        return chapter

    def delete_chapter(self, chapter: Chapter) -> None:
        self.db.delete(chapter)
        self.db.commit()

    def update_book(
        self,
        book: Book,
        title: str | None = None,
        genre: str | None = None,
        target_chapters: int | None = None,
        basic_idea: str | None = None,
        config: dict[str, Any] | None = None,
        memory_summary: str | None = None,
        style: str | None = None,
        current_chapter: int | None = None,
        status: str | None = None,
    ) -> Book:
        if title is not None:
            book.title = title
        if genre is not None:
            book.genre = genre
        if target_chapters is not None:
            book.target_chapters = target_chapters
        if basic_idea is not None:
            book.basic_idea = basic_idea
        if config is not None:
            book.config = config
        if memory_summary is not None:
            book.memory_summary = memory_summary
        if style is not None:
            book.style = style
        if current_chapter is not None:
            book.current_chapter = current_chapter
        if status is not None:
            book.status = status
        book.updated_at = get_china_now()
        self.db.commit()
        self.db.refresh(book)
        return book

    def create_book(
        self,
        title: str,
        genre: str,
        target_chapters: int,
        basic_idea: str,
        config: dict[str, Any],
        memory_summary: str = "",
        style: str = "",
    ) -> Book:
        book = Book(
            title=title,
            genre=genre,
            target_chapters=target_chapters,
            basic_idea=basic_idea,
            config=config,
            memory_summary=memory_summary,
            style=style,
            current_chapter=0,
        )
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        return book

    def delete_book(self, book: Book) -> None:
        self.db.query(Chapter).filter(Chapter.book_id == book.id).delete()
        self.db.delete(book)
        self.db.commit()

    def get_prev_ending(self, book_id: int, chapter_number: int, chars: int = 600) -> str:
        if chapter_number <= 1:
            return ""
        prev_chapter = self.get_chapter(book_id, chapter_number - 1)
        if not prev_chapter:
            return ""
        content = str(prev_chapter.content) if prev_chapter.content is not None else ""
        if not content:
            return ""
        return content[-chars:]
