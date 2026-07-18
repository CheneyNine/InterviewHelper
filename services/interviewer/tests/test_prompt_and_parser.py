import pytest

from app.model_client import ModelClientError, parse_json_object
from app.prompt import build_messages
from app.schemas import QuestionGenerationRequest


def request() -> QuestionGenerationRequest:
    return QuestionGenerationRequest(
        job_title="电商算法实习生",
        job_description="负责电商推荐与流量分发算法，支持直播业务和用户商品匹配。",
        job_requirements="机器学习基础扎实，熟悉算法与数据结构，有推荐、搜索或大模型项目经验。",
        interview_stage="技术面",
        question_count=5,
    )


def test_prompt_contains_all_job_inputs_and_stage_guidance():
    messages = build_messages(request())
    joined = "\n".join(message["content"] for message in messages)
    assert "电商算法实习生" in joined
    assert "推荐与流量分发算法" in joined
    assert "机器学习基础扎实" in joined
    assert "技术面" in joined
    assert "恰好包含 5 个元素" in joined
    assert "只输出一个合法 JSON 对象" in messages[0]["content"]


def test_parse_json_object_accepts_fenced_json_and_ignores_surrounding_text():
    value = parse_json_object('结果如下：\n```json\n{"questions": []}\n```')
    assert value == {"questions": []}


def test_parse_json_object_rejects_non_object():
    with pytest.raises(ModelClientError):
        parse_json_object("[1, 2, 3]")


def test_parse_model_response_supports_responses_and_anthropic_shapes():
    from app.model_client import _content_from_response

    assert _content_from_response({"output_text": '{"questions": []}'}) == '{"questions": []}'
    assert _content_from_response({"content": [{"type": "text", "text": '{"questions": []}'}]}) == '{"questions": []}'
