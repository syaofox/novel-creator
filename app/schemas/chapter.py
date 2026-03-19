from pydantic import BaseModel


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
    core_event: str
    chapter_number: int | None = None


class AddChapterRequest(BaseModel):
    position: int
    title: str
    core_event: str = ""
