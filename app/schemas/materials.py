from pydantic import BaseModel


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
