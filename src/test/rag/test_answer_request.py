import pytest
from pydantic import ValidationError

from market_intelligence_knowledge_graph.rag.schemas.answer_request import AnswerRequest, UserLevel


def test_defaults() -> None:
    request = AnswerRequest(question="삼전 실적")
    assert request.selected_entity_ids == ()
    assert request.level is UserLevel.INTERMEDIATE


def test_question_is_stripped() -> None:
    assert AnswerRequest(question="  삼전 실적  ").question == "삼전 실적"


def test_blank_question_rejected() -> None:
    # 공백만 있는 질문: strip 후 빈 문자열 -> min_length=1 위반
    with pytest.raises(ValidationError):
        AnswerRequest(question="   ")
