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


class ChapterBase(BaseModel):
    book_id: int
    chapter_number: int
    title: str
    core_event: str = ""
    status: str = "未完成"


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


class PlotSummaryBase(BaseModel):
    title: str
    content: str = ""


class PlotSummaryCreate(PlotSummaryBase):
    pass


class PlotSummaryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class PlotSummaryOut(PlotSummaryBase):
    id: int
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


class CharacterCardBase(BaseModel):
    title: str
    content: str = ""


class CharacterCardCreate(CharacterCardBase):
    pass


class CharacterCardUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class CharacterCardOut(CharacterCardBase):
    id: int
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


class WritingStyleBase(BaseModel):
    title: str
    content: str = ""


class WritingStyleCreate(WritingStyleBase):
    pass


class WritingStyleUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class WritingStyleOut(WritingStyleBase):
    id: int
    is_default: int
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True
