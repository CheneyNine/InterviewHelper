import pytest
from pydantic import ValidationError

from app.schemas import AnswerEvaluationRequest, GeneratedQuestion, QuestionGenerationRequest


def rubric():
    return [
        {
            "dimension": "技术准确性",
            "weight": 0.5,
            "description": "技术解释是否正确且符合题目约束。",
            "strong_signals": ["说明假设和权衡"],
            "partial_signals": ["方向正确但细节不足"],
            "missing_signals": ["出现关键概念错误"],
        },
        {
            "dimension": "证据具体性",
            "weight": 0.3,
            "description": "是否提供了个人行动、事实和可验证证据。",
            "strong_signals": ["说明个人行动和量化结果"],
            "partial_signals": ["提到经历但细节不足"],
            "missing_signals": ["只有抽象概念"],
        },
        {
            "dimension": "结构表达",
            "weight": 0.2,
            "description": "回答是否有清晰的起因、方法、结果和复盘。",
            "strong_signals": ["结构完整且逻辑连贯"],
            "partial_signals": ["主要步骤基本清楚"],
            "missing_signals": ["信息杂乱或无法跟随"],
        },
    ]


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


def test_question_generation_request_accepts_internal_request_id():
    value = QuestionGenerationRequest(
        request_id="trace-123",
        job_title="算法工程师",
        job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
        job_requirements="熟悉机器学习、数据结构和 Python，有推荐系统经验。",
    )
    assert value.request_id == "trace-123"


def test_question_generation_request_accepts_one_question_for_debugging():
    value = QuestionGenerationRequest(
        job_title="算法工程师",
        job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
        job_requirements="熟悉机器学习、数据结构和 Python，有推荐系统经验。",
        interview_stage="技术面",
        question_count=1,
    )
    assert value.question_count == 1


def test_generated_question_requires_reference_answer_and_rubric():
    question = GeneratedQuestion.model_validate(
        {
            "order": 1,
            "type": "technical",
            "prompt": "请说明你的推荐模型设计。",
            "purpose": "验证推荐建模能力",
            "competencies": ["machine_learning"],
            "expected_signals": ["说明目标和约束"],
            "follow_up_questions": [],
            "reference_answer": {
                "positioning": "先说明目标、数据和业务约束，再解释方法和验证。",
                "logic_paths": [
                    {
                        "title": "目标与约束",
                        "explanation": "先定义业务目标、数据条件和延迟约束。",
                        "key_points": ["目标指标", "数据范围"],
                    }
                ],
                "answer_outline": ["背景", "方法", "结果"],
                "evidence_to_include": ["个人行动", "量化结果"],
                "common_gaps": ["只讲概念，没有结果"],
            },
            "evaluation_rubric": rubric(),
        }
    )
    assert question.reference_answer.logic_paths[0].title == "目标与约束"
    assert question.evaluation_rubric[0].weight == 0.5


def test_answer_evaluation_request_accepts_multimodal_report():
    value = AnswerEvaluationRequest(
        job_title="算法工程师",
        job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
        question={
            "order": 1,
            "type": "technical",
            "prompt": "请说明你的推荐模型设计。",
            "purpose": "验证推荐建模能力",
            "competencies": ["machine_learning"],
            "expected_signals": ["说明目标和约束"],
            "reference_answer": {
                "positioning": "先说明目标、数据和业务约束，再解释方法和验证。",
                "logic_paths": [{"title": "目标", "explanation": "先定义业务目标和约束条件。", "key_points": ["指标"]}],
                "answer_outline": ["背景", "方法"],
                "evidence_to_include": ["个人行动"],
                "common_gaps": ["没有量化结果"],
            },
            "evaluation_rubric": rubric(),
        },
        multimodal_report={
            "answer_text": "我先定义目标指标，再设计召回和排序。",
            "voice_delivery_description": "语速较快，但整体清晰。",
            "observations": [{"code": "FAST_SPEECH", "message": "后半段语速快于前半段。"}],
        },
    )
    assert value.multimodal_report.answer_text.startswith("我先")


def test_question_generation_request_accepts_custom_stage_but_rejects_out_of_range_count():
    with pytest.raises(ValidationError):
        QuestionGenerationRequest(
            job_title="算法工程师",
            job_description="负责推荐系统策略和在线服务，持续优化业务指标。",
            job_requirements="熟悉机器学习、数据结构和 Python，有推荐系统经验。",
            interview_stage="复试-算法专项技术面",
            question_count=20,
        )
