from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


QuestionType = Literal["behavioral", "technical", "situational"]


class QuestionGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_title: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=20, max_length=12000)
    job_requirements: str = Field(..., min_length=10, max_length=12000)
    # Keep this open-ended so the UI can add variants such as “复试-技术面”
    # without requiring a backend deployment. Prompt guidance falls back to 初试.
    interview_stage: str = Field(default="初试", min_length=2, max_length=40)
    question_count: int = Field(default=5, ge=3, le=10)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)

    @field_validator("job_title", "job_description", "job_requirements")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("interview_stage")
    @classmethod
    def strip_stage(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("interview_stage must not be blank")
        return value


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int = Field(..., ge=1)
    type: QuestionType
    prompt: str = Field(..., min_length=8, max_length=500)
    purpose: str = Field(..., min_length=4, max_length=300)
    competencies: list[str] = Field(..., min_length=1, max_length=5)
    expected_signals: list[str] = Field(..., min_length=1, max_length=8)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=3)


class GeneratedQuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[GeneratedQuestion] = Field(..., min_length=3, max_length=10)
    model: str
    prompt_version: str
