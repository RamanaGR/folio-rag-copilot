from typing import Any, Literal

from pydantic import BaseModel, Field


class FormField(BaseModel):
    label: str
    field_type: str
    selector_hint: str = ""
    options: list[str] = Field(default_factory=list)
    required: bool = False


class RoleContext(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""
    url: str = ""
    hostname: str = ""


class ResolveFormRequest(BaseModel):
    fields: list[FormField] = Field(default_factory=list)
    context: RoleContext = Field(default_factory=RoleContext)


class FieldAnswer(BaseModel):
    value: str = ""
    confidence: float = 0.0
    needs_human: bool = True
    reason: str = "Not in profile"


class ResolvedField(BaseModel):
    label: str
    answer: FieldAnswer


class ResolveFormResponse(BaseModel):
    answers: list[ResolvedField]


class LearnRequest(BaseModel):
    question_label: str
    field_type: str
    options: list[str] = Field(default_factory=list)
    user_value: str
    domain: str = ""
    selector_hint: str = ""


class LearnResponse(BaseModel):
    learned: bool
    message: str
    confidence: float = 1.0


class CoverLetterRequest(BaseModel):
    context: RoleContext
    output: Literal["text", "pdf"] = "text"


class CoverLetterResponse(BaseModel):
    text: str
    filename: str = "cover-letter.pdf"
    content_base64: str | None = None


class HealthResponse(BaseModel):
    status: str
    ollama_url: str
    memory_count: int
