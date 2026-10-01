import pytest

from assignment_autopsy.ai.parsing import parse_evaluation


def test_parse_level_evaluation() -> None:
    result = parse_evaluation(
        '{"requirements":[],"rubric":[{"type":"level","criterion_id":"c","estimated_min_level":"A","estimated_max_level":"B","confidence":0.8,"evidence":["text"],"explanation":"x"}],"summary":"x","disclaimer":"teacher decides"}'
    )
    assert result.rubric[0].criterion_id == "c"


def test_parse_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_evaluation("not json")
