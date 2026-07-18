import pytest
from pydantic import ValidationError

from app.schemas import QuestionGenerationRequest


def test_question_generation_request_accepts_stage_and_inputs():
    value = QuestionGenerationRequest(
        job_title="算法工程师",
        job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
        job_requirements="熟悉机器学习、数据结构和 Python，有推荐系统经验。",
        interview_stage="业务面",
        question_count=6,
    )
    assert value.question_count == 6
    assert value.interview_stage == "业务面"


def test_question_generation_request_accepts_custom_stage_but_rejects_out_of_range_count():
    with pytest.raises(ValidationError):
        QuestionGenerationRequest(
            job_title="算法工程师",
            job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
            job_requirements="熟悉机器学习、数据结构和 Python，有推荐系统经验。",
            interview_stage="复试-算法专项技术面",
            question_count=20,
        )
