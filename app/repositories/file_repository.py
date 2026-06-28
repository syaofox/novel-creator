import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
BOOKS_DIR = Path("books")


def _china_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


# ── Pydantic models ──────────────────────────────────────────────────


class Book(BaseModel):
    id: int
    title: str = ""
    genre: str = ""
    target_chapters: int = 3
    basic_idea: str = ""
    config: dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.78, "top_p": 0.92, "max_tokens": 16384, "stream": True,
        "jailbreak_prefix": "", "system_template": "",
    })
    memory_summary: str = ""
    style: str = ""
    current_chapter: int = 0
    status: str = "进行中"
    created_at: str = ""
    updated_at: str = ""


class Chapter(BaseModel):
    id: int
    book_id: int
    chapter_number: int
    title: str = ""
    core_event: str = ""
    content: str = ""
    status: str = "未完成"
    created_at: str = ""


class GlobalConfig(BaseModel):
    id: int = 1
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    default_model: str = "deepseek-v4-pro"
    temperature: float = 0.78
    top_p: float = 0.92
    max_tokens: int = 16384
    stream: bool = True
    jailbreak_prefix: str = ""
    system_template: str = ""


class PlotSummary(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class CharacterCard(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class WritingStyle(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    is_default: int = 0
    created_at: str = ""
    updated_at: str = ""


class MaterialNote(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class BookInitData(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    book_title: str = ""
    created_at: str = ""
    updated_at: str = ""


# ── File Repository ──────────────────────────────────────────────────


class FileRepository:
    """File-based storage replacing SQLAlchemy + SQLite.

    Directory layout:
      data/
        ids.json                 # {entity_type: next_id}
        global_config.json
        materials/
          plot_summaries/{id}.json
          character_cards/{id}.json
          writing_styles/{id}.json
          material_notes/{id}.json
          book_init_data/{id}.json
      books/{book_id}/
        meta.json
        chapters/{num}.json
    """

    def __init__(self, data_dir: str | Path = "data", books_dir: str | Path = "books"):
        self.data_dir = Path(data_dir)
        self.books_dir = Path(books_dir)
        self._ensure_dirs()

    # ── path helpers ──────────────────────────────────────────────

    def _ensure_dirs(self):
        for d in [
            self.data_dir / "materials" / "plot_summaries",
            self.data_dir / "materials" / "character_cards",
            self.data_dir / "materials" / "writing_styles",
            self.data_dir / "materials" / "material_notes",
            self.data_dir / "materials" / "book_init_data",
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def _book_dir(self, book_id: int) -> Path:
        return self.books_dir / str(book_id)

    def _book_chapters_dir(self, book_id: int) -> Path:
        return self._book_dir(book_id) / "chapters"

    # ── id management ─────────────────────────────────────────────

    def _ids_path(self) -> Path:
        return self.data_dir / "ids.json"

    def _load_ids(self) -> dict[str, int]:
        path = self._ids_path()
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _save_ids(self, ids: dict[str, int]):
        with open(self._ids_path(), "w") as f:
            json.dump(ids, f, indent=2, ensure_ascii=False)

    def _next_id(self, entity: str) -> int:
        ids = self._load_ids()
        n = ids.get(entity, 0) + 1
        ids[entity] = n
        self._save_ids(ids)
        return n

    # ── generic read / write ──────────────────────────────────────

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    def _list_json(self, directory: Path) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        results = []
        for fname in sorted(directory.iterdir()):
            if fname.suffix == ".json" and fname.stem != "_meta":
                data = self._read_json(fname)
                if data:
                    results.append(data)
        return results

    # ── Book operations ───────────────────────────────────────────

    def get_book(self, book_id: int) -> Book | None:
        path = self._book_dir(book_id) / "meta.json"
        data = self._read_json(path)
        if data is None:
            return None
        try:
            return Book(**data)
        except Exception as e:
            logger.warning(f"Failed to parse book {book_id}: {e}")
            return None

    def get_books(self, status: str | None = None) -> list[Book]:
        if not self.books_dir.exists():
            return []
        all_books = []
        for entry in sorted(self.books_dir.iterdir()):
            if entry.is_dir() and entry.name.isdigit():
                book = self.get_book(int(entry.name))
                if book:
                    all_books.append(book)
        if status:
            all_books = [b for b in all_books if b.status == status]
        all_books.sort(key=lambda b: b.updated_at, reverse=True)
        return all_books

    def create_book(self, book: Book) -> Book:
        if book.id == 0:
            book.id = self._next_id("book")
        now = _china_now()
        book.created_at = now
        book.updated_at = now
        book_dir = self._book_dir(book.id)
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / "chapters").mkdir(exist_ok=True)
        self._write_json(book_dir / "meta.json", book.model_dump())
        return book

    def update_book(self, book: Book) -> Book:
        book.updated_at = _china_now()
        self._write_json(self._book_dir(book.id) / "meta.json", book.model_dump())
        return book

    def delete_book(self, book_id: int):
        path = self._book_dir(book_id)
        if path.exists():
            shutil.rmtree(path)

    # ── Chapter operations ────────────────────────────────────────

    def get_chapter(self, book_id: int, chapter_number: int) -> Chapter | None:
        path = self._book_chapters_dir(book_id) / f"{chapter_number}.json"
        data = self._read_json(path)
        if data is None:
            return None
        try:
            return Chapter(**data)
        except Exception as e:
            logger.warning(f"Failed to parse chapter {book_id}/{chapter_number}: {e}")
            return None

    def get_chapters(self, book_id: int) -> list[Chapter]:
        results = []
        for data in self._list_json(self._book_chapters_dir(book_id)):
            try:
                results.append(Chapter(**data))
            except Exception as e:
                logger.warning(f"Failed to parse chapter: {e}")
        results.sort(key=lambda c: c.chapter_number)
        return results

    def create_chapter(
        self,
        book_id: int,
        chapter_number: int,
        title: str = "",
        content: str = "",
        core_event: str = "",
        status: str = "未完成",
    ) -> Chapter:
        chapter = Chapter(
            id=self._next_id("chapter"),
            book_id=book_id,
            chapter_number=chapter_number,
            title=title,
            content=content,
            core_event=core_event,
            status=status,
            created_at=_china_now(),
        )
        self._write_json(
            self._book_chapters_dir(book_id) / f"{chapter_number}.json",
            chapter.model_dump(),
        )
        return chapter

    def update_chapter(
        self,
        chapter: Chapter,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
    ) -> Chapter:
        if title is not None:
            chapter.title = title
        if content is not None:
            chapter.content = content
        if status is not None:
            chapter.status = status
        self._write_json(
            self._book_chapters_dir(chapter.book_id) / f"{chapter.chapter_number}.json",
            chapter.model_dump(),
        )
        return chapter

    def delete_chapter(self, chapter: Chapter):
        path = self._book_chapters_dir(chapter.book_id) / f"{chapter.chapter_number}.json"
        if path.exists():
            path.unlink()

    def get_latest_chapter(self, book_id: int) -> Chapter | None:
        chapters = self.get_chapters(book_id)
        return chapters[-1] if chapters else None

    def get_max_chapter_number(self, book_id: int) -> int:
        latest = self.get_latest_chapter(book_id)
        return latest.chapter_number if latest else 0

    def get_prev_ending(self, book_id: int, chapter_number: int, chars: int = 600) -> str:
        if chapter_number <= 1:
            return ""
        prev = self.get_chapter(book_id, chapter_number - 1)
        if not prev or not prev.content:
            return ""
        return prev.content[-chars:]

    def renumber_chapters(self, book_id: int, start_from: int, offset: int = 1):
        chapters_dir = self._book_chapters_dir(book_id)
        chapters = self.get_chapters(book_id)
        if offset > 0:
            chapters.reverse()
        for ch in chapters:
            if ch.chapter_number >= start_from:
                old_path = chapters_dir / f"{ch.chapter_number}.json"
                ch.chapter_number = ch.chapter_number + offset
                self._write_json(chapters_dir / f"{ch.chapter_number}.json", ch.model_dump())
                if old_path.exists():
                    old_path.unlink()

    def insert_chapter_at(self, book_id: int, position: int, title: str, core_event: str = "") -> Chapter:
        self.renumber_chapters(book_id, position)
        chapter = self.create_chapter(
            book_id=book_id,
            chapter_number=position,
            title=title,
            core_event=core_event,
        )
        return chapter

    # ── GlobalConfig ──────────────────────────────────────────────

    def get_global_config(self) -> GlobalConfig:
        path = self.data_dir / "global_config.json"
        data = self._read_json(path)
        if data:
            return GlobalConfig(**data)
        config = GlobalConfig()
        self._write_json(path, config.model_dump())
        return config

    def save_global_config(self, config: GlobalConfig) -> GlobalConfig:
        self._write_json(self.data_dir / "global_config.json", config.model_dump())
        return config

    # ── Materials (PlotSummary) ───────────────────────────────────

    def _material_dir(self, entity: str) -> Path:
        return self.data_dir / "materials" / entity

    def _material_list(self, model_cls: type, entity: str) -> list:
        results = []
        for data in self._list_json(self._material_dir(entity)):
            try:
                results.append(model_cls(**data))
            except Exception as e:
                logger.warning(f"Failed to parse {entity}: {e}")
        results.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
        return results

    def _material_create(self, model_cls: type, entity: str, data: dict) -> Any:
        data["id"] = self._next_id(entity)
        now = _china_now()
        data.setdefault("created_at", now)
        data["updated_at"] = now
        obj = model_cls(**data)
        self._write_json(self._material_dir(entity) / f"{obj.id}.json", obj.model_dump())
        return obj

    def _material_update(self, model_cls: type, entity: str, item_id: int, data: dict) -> Any | None:
        path = self._material_dir(entity) / f"{item_id}.json"
        existing = self._read_json(path)
        if existing is None:
            return None
        existing.update(data)
        existing["updated_at"] = _china_now()
        self._write_json(path, existing)
        return model_cls(**existing)

    def _material_delete(self, entity: str, item_id: int) -> bool:
        path = self._material_dir(entity) / f"{item_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def _material_get(self, model_cls: type, entity: str, item_id: int) -> Any | None:
        path = self._material_dir(entity) / f"{item_id}.json"
        data = self._read_json(path)
        if data is None:
            return None
        return model_cls(**data)

    # PlotSummary
    def get_plot_summaries(self) -> list[PlotSummary]:
        return self._material_list(PlotSummary, "plot_summaries")

    def get_plot_summary(self, item_id: int) -> PlotSummary | None:
        return self._material_get(PlotSummary, "plot_summaries", item_id)

    def create_plot_summary(self, **data) -> PlotSummary:
        return self._material_create(PlotSummary, "plot_summaries", data)

    def update_plot_summary(self, item_id: int, **data) -> PlotSummary | None:
        return self._material_update(PlotSummary, "plot_summaries", item_id, data)

    def delete_plot_summary(self, item_id: int) -> bool:
        return self._material_delete("plot_summaries", item_id)

    # CharacterCard
    def get_character_cards(self) -> list[CharacterCard]:
        return self._material_list(CharacterCard, "character_cards")

    def get_character_card(self, item_id: int) -> CharacterCard | None:
        return self._material_get(CharacterCard, "character_cards", item_id)

    def create_character_card(self, **data) -> CharacterCard:
        return self._material_create(CharacterCard, "character_cards", data)

    def update_character_card(self, item_id: int, **data) -> CharacterCard | None:
        return self._material_update(CharacterCard, "character_cards", item_id, data)

    def delete_character_card(self, item_id: int) -> bool:
        return self._material_delete("character_cards", item_id)

    # WritingStyle
    def get_writing_styles(self) -> list[WritingStyle]:
        return self._material_list(WritingStyle, "writing_styles")

    def get_writing_style(self, item_id: int) -> WritingStyle | None:
        return self._material_get(WritingStyle, "writing_styles", item_id)

    def create_writing_style(self, **data) -> WritingStyle:
        return self._material_create(WritingStyle, "writing_styles", data)

    def update_writing_style(self, item_id: int, **data) -> WritingStyle | None:
        return self._material_update(WritingStyle, "writing_styles", item_id, data)

    def delete_writing_style(self, item_id: int) -> bool:
        return self._material_delete("writing_styles", item_id)

    # MaterialNote
    def get_material_notes(self) -> list[MaterialNote]:
        return self._material_list(MaterialNote, "material_notes")

    def get_material_note(self, item_id: int) -> MaterialNote | None:
        return self._material_get(MaterialNote, "material_notes", item_id)

    def create_material_note(self, **data) -> MaterialNote:
        return self._material_create(MaterialNote, "material_notes", data)

    def update_material_note(self, item_id: int, **data) -> MaterialNote | None:
        return self._material_update(MaterialNote, "material_notes", item_id, data)

    def delete_material_note(self, item_id: int) -> bool:
        return self._material_delete("material_notes", item_id)

    # BookInitData
    def get_book_init_data_list(self) -> list[BookInitData]:
        return self._material_list(BookInitData, "book_init_data")

    def get_book_init_data(self, item_id: int) -> BookInitData | None:
        return self._material_get(BookInitData, "book_init_data", item_id)

    def create_book_init_data(self, **data) -> BookInitData:
        return self._material_create(BookInitData, "book_init_data", data)

    def update_book_init_data(self, item_id: int, **data) -> BookInitData | None:
        return self._material_update(BookInitData, "book_init_data", item_id, data)

    def delete_book_init_data(self, item_id: int) -> bool:
        return self._material_delete("book_init_data", item_id)

    # ── helpers ───────────────────────────────────────────────────

    def as_dict(self, data: list[BaseModel]) -> list[dict[str, Any]]:
        return [d.model_dump() if hasattr(d, "model_dump") else d for d in data]
