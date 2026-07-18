from app.main import aggregate, report_to_multimodal


def test_report_mapping_preserves_transcript_metrics_and_limitations():
    report = {
        "analysis": {
            "transcript": {"text": "回答内容"},
            "delivery": {"metrics": {"words_per_minute": 180}, "observations": []},
            "video": {"observations": [{"code": "FACE", "message": "人脸可见"}], "unavailable_reasons": []},
            "observable_state": {"summary": "证据不足", "evidence": []},
        },
        "formatted_report": {"dimensions": [{"key": "visible_expression", "summary": "表情证据不足"}]},
    }
    mapped = report_to_multimodal(report)
    assert mapped["answer_text"] == "回答内容"
    assert mapped["metrics"]["words_per_minute"] == 180
    assert mapped["body_language_description"] == "人脸可见"
    assert "证据不足" in mapped["limitations"]


def test_empty_aggregate_has_null_scores():
    result = aggregate("missing-interview")
    assert result["question_analyses"] == []
    assert result["aggregate_scores"] == {"overall_score": None, "content_score": None, "delivery_score": None}
