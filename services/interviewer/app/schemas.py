from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


QuestionType = Literal["behavioral", "technical", "situational"]


class QuestionGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_title: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=20, max_length=12000)
    job_requirements: str = Field(..., min_length=10, max_length=12000)
    # Keep this open-ended so the UI can add variants such as “复试-技术面”
    # without requiring a backend deployment. Prompt guidance falls back to 初试.
    interview_stage: str = Field(default="初试", min_length=2, max_length=40)
    question_count: int = Field(default=5, ge=1, le=10)
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
    reference_answer: "ReferenceAnswer"
    evaluation_rubric: list["RubricCriterion"] = Field(..., min_length=3, max_length=8)


class LogicPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=2, max_length=100)
    explanation: str = Field(..., min_length=8, max_length=500)
    key_points: list[str] = Field(..., min_length=1, max_length=6)


class ReferenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positioning: str = Field(..., min_length=8, max_length=300)
    logic_paths: list[LogicPath] = Field(..., min_length=1, max_length=4)
    answer_outline: list[str] = Field(..., min_length=2, max_length=8)
    evidence_to_include: list[str] = Field(..., min_length=1, max_length=8)
    common_gaps: list[str] = Field(..., min_length=1, max_length=6)


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(..., min_length=2, max_length=80)
    weight: float = Field(..., ge=0, le=1)
    description: str = Field(..., min_length=8, max_length=300)
    strong_signals: list[str] = Field(..., min_length=1, max_length=6)
    partial_signals: list[str] = Field(..., min_length=1, max_length=6)
    missing_signals: list[str] = Field(..., min_length=1, max_length=6)


class GeneratedQuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[GeneratedQuestion] = Field(..., min_length=1, max_length=10)
    model: str
    prompt_version: str


class ReportObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=2, max_length=80)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    message: str = Field(..., min_length=2, max_length=500)


class MultimodalAnswerReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    answer_text: str = Field(..., min_length=1, max_length=20000)
    facial_behavior_description: str | None = Field(default=None, max_length=4000)
    body_language_description: str | None = Field(default=None, max_length=4000)
    voice_delivery_description: str | None = Field(default=None, max_length=4000)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    observations: list[ReportObservation] = Field(default_factory=list, max_length=100)


class AnswerEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    job_title: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=20, max_length=12000)
    question: GeneratedQuestion
    multimodal_report: MultimodalAnswerReport
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)


class TranscriptEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    job_title: str | None = Field(default=None, max_length=200)
    question_prompt: str = Field(..., min_length=8, max_length=500)
    answer_text: str = Field(..., min_length=1, max_length=20000)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)


class TranscriptEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance_score: float = Field(..., ge=0, le=1)
    clarity_score: float = Field(..., ge=0, le=1)
    fluency_score: float = Field(..., ge=0, le=1)
    structure_score: float = Field(..., ge=0, le=1)
    summary: str = Field(..., min_length=4, max_length=800)
    strengths: list[str] = Field(..., min_length=1, max_length=8)
    improvements: list[str] = Field(..., min_length=1, max_length=8)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=6)


class ReferenceComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    job_title: str | None = Field(default=None, max_length=200)
    question: GeneratedQuestion
    answer_text: str = Field(..., min_length=1, max_length=20000)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)


class ReferenceComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alignment_score: float = Field(..., ge=0, le=1)
    correctness_score: float = Field(..., ge=0, le=1)
    covered_key_points: list[str] = Field(default_factory=list, max_length=8)
    missing_key_points: list[str] = Field(default_factory=list, max_length=8)
    comparison_summary: str = Field(..., min_length=4, max_length=800)
    improved_answer_outline: list[str] = Field(..., min_length=2, max_length=8)
    improvement_advice: list[str] = Field(..., min_length=1, max_length=8)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=6)


class EvaluationDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(..., min_length=2, max_length=80)
    score: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)
    rationale: str = Field(..., min_length=4, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=6)


class DetailedDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=2, max_length=80)
    title: str = Field(..., min_length=2, max_length=80)
    score: float | None = Field(default=None, ge=0, le=1)
    summary: str = Field(..., min_length=2, max_length=600)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    suggestions: list[str] = Field(default_factory=list, max_length=6)
    limitations: list[str] = Field(default_factory=list, max_length=4)


class AnswerEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: float = Field(..., ge=0, le=1)
    dimension_analysis: list[DetailedDimension] = Field(..., min_length=8, max_length=8)
    strengths: list[str] = Field(..., min_length=1, max_length=8)
    improvements: list[str] = Field(..., min_length=1, max_length=8)
    evidence: list[str] = Field(..., min_length=1, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=6)
    disclaimer: str = "这是基于题目、回答文本和可观察表现的训练反馈，不是心理、医学或招聘结论。"


class QuestionAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_order: int = Field(..., ge=1)
    question_id: str = Field(..., min_length=1, max_length=100)
    answer_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=8, max_length=500)
    overall_score: float | None = Field(default=None, ge=0, le=1)
    dimension_scores: dict[str, float | None] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    improvements: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=6)
    dimension_analysis: list[DetailedDimension] = Field(default_factory=list, max_length=8)


class InterviewReportGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    interview_id: str = Field(..., min_length=1, max_length=100)
    job_title: str = Field(..., min_length=1, max_length=200)
    interview_stage: str = Field(..., min_length=2, max_length=40)
    question_analyses: list[QuestionAnalysisSummary] = Field(..., min_length=1, max_length=20)
    aggregate_scores: dict[str, float | None] = Field(default_factory=dict)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)


class InterviewReportDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=8, max_length=1000)
    strengths: list[str] = Field(..., min_length=1, max_length=8)
    priority_improvements: list[str] = Field(..., min_length=1, max_length=8)
    practice_plan: list[str] = Field(..., min_length=1, max_length=8)
    dimension_analysis: list[DetailedDimension] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    disclaimer: str = "这些结果是训练建议，不是心理、医学或招聘结论。"
