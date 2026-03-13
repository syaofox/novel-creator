from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    temperature: float = Field(0.78, ge=0, le=2)
    top_p: float = Field(0.92, ge=0, le=1)
    max_tokens: int = Field(8192, ge=1, le=32768)
    jailbreak_prefix: str
    system_template: str
