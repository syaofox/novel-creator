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
    style: str | None = None
    status: str | None = None


class BookOut(BookBase):
    id: int
    config: dict[str, Any]
    memory_summary: str
    style: str
    current_chapter: int
    status: str
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True
