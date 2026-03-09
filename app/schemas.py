from pydantic import BaseModel, Field
from typing import Any


class BookBase(BaseModel):
    title: str
    genre: str
    target_chapters: int
    basic_idea: str


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: str | None = None
    genre: str | None = None
    target_chapters: int | None = None
    config: dict[str, Any] | None = None
    memory_summary: str | None = None
    status: str | None = None


class BookOut(BookBase):
    id: int
    config: dict[str, Any]
    memory_summary: str
    current_chapter: int
    status: str
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


class ChapterBase(BaseModel):
    book_id: int
    chapter_number: int
    title: str


class ChapterCreate(ChapterBase):
    pass


class ChapterOut(ChapterBase):
    id: int
    created_at: str

    class Config:
        from_attributes = True


class WriteChapterRequest(BaseModel):
    core_event: str = Field(..., description="本章核心事件")


class SettingsUpdate(BaseModel):
    temperature: float = Field(0.78, ge=0, le=2)
    top_p: float = Field(0.92, ge=0, le=1)
    max_tokens: int = Field(8192, ge=1, le=32768)
    jailbreak_prefix: str
    system_template: str
