"""RoutePlanner 단위 테스트. 순수 판단 로직이라 표 형태로 경우를 고정한다."""

# LinkResult, LinkedEntity, LinkStatus: C1-1 DTO 경로로 import

from market_intelligence_knowledge_graph.rag.classification.planner import ClarifyPlan, DeclinePlan, RetrievePlan, RoutePlanner
from market_intelligence_knowledge_graph.rag.schemas.answer_event import ClarifyReason, DeclineReason
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification, QuestionType
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import (
    LinkResult,
    LinkStatus,
    LinkedEntity,
    MatchedBy,
)

SAMSUNG = LinkedEntity(entity_id="dart:00126380", name="삼성전자(주)", matched_alias="삼전", matched_by=MatchedBy.ALIAS)
HYNIX = LinkedEntity(entity_id="dart:00164779", name="SK하이닉스(주)", matched_alias="하닉", matched_by=MatchedBy.ALIAS)

NOT_FOUND = LinkResult(status=LinkStatus.NOT_FOUND, entities=())
CONFIRMED = LinkResult(status=LinkStatus.CONFIRMED, entities=(SAMSUNG,))
MULTIPLE = LinkResult(status=LinkStatus.MULTIPLE, entities=(SAMSUNG, HYNIX))
AMBIGUOUS = LinkResult(status=LinkStatus.AMBIGUOUS, entities=(SAMSUNG, HYNIX))

MIN_CONFIDENCE = 0.6  # 테스트에선 값을 고정 (config가 바뀌어도 테스트 의도 유지)
planner = RoutePlanner(min_confidence=MIN_CONFIDENCE)  # 상태 없는 객체라 모듈 전체 공유


def cls(question_type: QuestionType, confidence: float = 1.0) -> Classification:
    """분류 결과 생성 헬퍼."""
    return Classification(type=question_type, confidence=confidence)


# ---- 링크 상태 분기 (C1-8에서 이동) ----
def test_not_found_clarifies() -> None:
    assert planner.plan(cls(QuestionType.T1), NOT_FOUND) == ClarifyPlan(reason=ClarifyReason.NOT_FOUND, candidates=())


def test_ambiguous_keeps_candidates() -> None:
    assert planner.plan(cls(QuestionType.T1), AMBIGUOUS) == ClarifyPlan(
        reason=ClarifyReason.AMBIGUOUS, candidates=(SAMSUNG, HYNIX)
    )


def test_multiple_asks_one_by_one() -> None:
    assert planner.plan(cls(QuestionType.T1), MULTIPLE) == ClarifyPlan(
        reason=ClarifyReason.MULTIPLE_UNSUPPORTED, candidates=(SAMSUNG, HYNIX)
    )


def test_confirmed_retrieves() -> None:
    assert planner.plan(cls(QuestionType.T1), CONFIRMED) == RetrievePlan(
        retriever_names=("filing_chunks",), entity=SAMSUNG
    )


# ---- 유형 분기 (C1-8b 신규) ----
def test_t7_declines_as_advice() -> None:
    assert planner.plan(cls(QuestionType.T7), CONFIRMED) == DeclinePlan(reason=DeclineReason.INVESTMENT_ADVICE)


def test_decline_comes_before_clarify() -> None:
    # 회사를 못 찾았어도 범위 밖이면 되묻지 않고 바로 거절
    assert planner.plan(cls(QuestionType.T8), NOT_FOUND) == DeclinePlan(reason=DeclineReason.OUT_OF_SCOPE)


def test_unsupported_type() -> None:
    assert planner.plan(cls(QuestionType.T9), CONFIRMED) == DeclinePlan(reason=DeclineReason.NOT_SUPPORTED_YET)


def test_low_confidence_falls_back_to_t1() -> None:
    # 애매한 T7 판정으로 정상 질문을 막지 않음: T1로 간주해 검색 진행
    plan = planner.plan(cls(QuestionType.T7, confidence=0.3), CONFIRMED)
    assert isinstance(plan, RetrievePlan)


def test_confidence_boundary_uses_type() -> None:
    # 경계값: 임계값과 같으면 "미만"이 아니므로 분류 유형 그대로 사용
    plan = planner.plan(cls(QuestionType.T7, confidence=MIN_CONFIDENCE), CONFIRMED)
    assert plan == DeclinePlan(reason=DeclineReason.INVESTMENT_ADVICE)
