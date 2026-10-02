"""RagService·plan_route 단위 테스트.

가짜 분류기·링커·검색기·생성기를 끼워서 LLM, OpenSearch, Neo4j 없이 흐름만 검증한다.
"""

import asyncio

import pytest

from market_intelligence_knowledge_graph.rag.classification.classfier import StubQuestionClassifier
from market_intelligence_knowledge_graph.rag.classification.planner import (
    RoutePlanner,
)
from market_intelligence_knowledge_graph.rag.schemas.answer_event import (
    ClarificationEvent,
    ClarifyReason,
    DeclineEvent,
    EntityCorrectionEvent,
)
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification, QuestionType
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import (
    LinkResult,
    LinkStatus,
    LinkedEntity,
    MatchedBy,
)
from market_intelligence_knowledge_graph.rag.orchestration import rag_service as rag_service_module
from market_intelligence_knowledge_graph.rag.orchestration.rag_service import RagService
from market_intelligence_knowledge_graph.rag.schemas.answer_event import DoneEvent
from market_intelligence_knowledge_graph.rag.schemas.answer_request import AnswerRequest

SAMSUNG = LinkedEntity(entity_id="dart:00126380", name="삼성전자(주)", matched_alias="삼전")
HYNIX = LinkedEntity(entity_id="dart:00164779", name="SK하이닉스(주)", matched_alias="하닉")
MICRON_GUESSED = LinkedEntity(
    entity_id="cik:0000723125", name="Micron Technology", matched_alias="마이크런", matched_by=MatchedBy.LLM_GUESS
)

NOT_FOUND = LinkResult(status=LinkStatus.NOT_FOUND, entities=())
CONFIRMED = LinkResult(status=LinkStatus.CONFIRMED, entities=(SAMSUNG,))
MULTIPLE = LinkResult(status=LinkStatus.MULTIPLE, entities=(SAMSUNG, HYNIX))


# ---------------------------------------------------------------- 가짜 의존성
class FakeClassifier:
    """정해둔 분류 결과를 돌려줌."""

    def __init__(self, classification: Classification) -> None:
        self._classification = classification

    async def classify(self, question: str) -> Classification:
        return self._classification


class FakeLinker:
    """정해둔 LinkResult를 돌려주고, 어떤 메서드가 불렸는지 기록."""

    def __init__(self, result: LinkResult) -> None:
        self._result = result
        self.link_calls = 0
        self.resolve_calls: list[tuple[str, ...]] = []

    async def link(self, question, mentions=()):
        self.link_calls += 1
        return self._result

    async def resolve_ids(self, entity_ids):
        self.resolve_calls.append(entity_ids)
        return self._result


class FakeRetriever:
    name = "filing_chunks"  # FilingChunkRetriever.name과 같아야 planner가 고름

    def __init__(self, items: list | None = None) -> None:
        self.calls: list = []
        self._items = items or []

    async def retrieve(self, query):
        self.calls.append(query)
        return self._items


class GenerateSpy:
    """generate_answer 대체: 받은 items 기록 + 표식 이벤트 하나."""

    def __init__(self) -> None:
        self.received_items: list | None = None

    async def __call__(self, question, items):
        self.received_items = items
        yield "GENERATED"


@pytest.fixture
def generate_spy(monkeypatch: pytest.MonkeyPatch) -> GenerateSpy:
    spy = GenerateSpy()
    monkeypatch.setattr(rag_service_module, "generate_answer", spy)  # rag_service 모듈 안의 이름 교체
    return spy


def make_service(
    link: LinkResult,
    retrievers: list | None = None,
    question_type: QuestionType = QuestionType.T1,
    linker: FakeLinker | None = None,
) -> RagService:
    return RagService(
        classifier=FakeClassifier(Classification(type=question_type, confidence=1.0)),
        linker=linker or FakeLinker(link),
        route_planner=RoutePlanner(min_confidence=0.6),  # 실제 planner 사용: 흐름 + 판단 연결까지 검증
        retrievers=retrievers if retrievers is not None else [FakeRetriever()],
    )


def collect(service: RagService, question: str, selected: tuple[str, ...] = ()) -> list:
    async def _run():
        request = AnswerRequest(question=question, selected_entity_ids=selected)
        return [e async for e in service.response_answer_stream(request)]

    return asyncio.run(_run())


# ---------------------------------------------------------------- 되묻기 (C1-8 유지)
def test_not_found_clarifies_and_ends(generate_spy) -> None:
    retriever = FakeRetriever()
    events = collect(make_service(NOT_FOUND, [retriever]), "반도체 리스크")
    assert [type(e) for e in events] == [ClarificationEvent, DoneEvent]
    assert retriever.calls == []
    assert generate_spy.received_items is None


def test_multiple_returns_candidates(generate_spy) -> None:
    events = collect(make_service(MULTIPLE), "삼전이랑 하닉 실적")
    assert events[0].reason is ClarifyReason.MULTIPLE_UNSUPPORTED
    assert [c.entity_id for c in events[0].candidates] == [SAMSUNG.entity_id, HYNIX.entity_id]


def test_clarify_message_includes_unresolved(generate_spy) -> None:
    link = LinkResult(status=LinkStatus.NOT_FOUND, entities=(), unresolved_mentions=("XYZ전자",))
    events = collect(make_service(link), "XYZ전자 실적")
    assert "XYZ전자" in events[0].message  # 사용자가 뭘 고쳐야 할지 문구에 드러나야 함


# ---------------------------------------------------------------- 거절 (C1-8b)
def test_decline_skips_search_and_llm(generate_spy) -> None:
    retriever = FakeRetriever()
    events = collect(make_service(CONFIRMED, [retriever], question_type=QuestionType.T7), "엔비디아 사도 돼?")
    assert [type(e) for e in events] == [DeclineEvent, DoneEvent]
    assert retriever.calls == []
    assert generate_spy.received_items is None


# ---------------------------------------------------------------- 검색 경로
def test_confirmed_searches_with_linked_entity(generate_spy) -> None:
    retriever = FakeRetriever(items=["item1", "item2"])
    events = collect(make_service(CONFIRMED, [retriever]), "삼전 실적")
    assert retriever.calls[0].entity_id == SAMSUNG.entity_id
    assert generate_spy.received_items == ["item1", "item2"]
    assert events == ["GENERATED"]  # ALIAS 확정이면 보정 알림 없음


def test_llm_guess_emits_correction_first(generate_spy) -> None:
    link = LinkResult(status=LinkStatus.CONFIRMED, entities=(MICRON_GUESSED,))
    events = collect(make_service(link), "마이크런 실적")
    assert isinstance(events[0], EntityCorrectionEvent)  # 답변보다 먼저
    assert events[0].corrections[0].surface == "마이크런"
    assert events[1:] == ["GENERATED"]


def test_selected_ids_use_resolve_not_link(generate_spy) -> None:
    linker = FakeLinker(CONFIRMED)
    collect(make_service(CONFIRMED, linker=linker), "삼성 실적", selected=(SAMSUNG.entity_id,))
    assert linker.resolve_calls == [(SAMSUNG.entity_id,)]
    assert linker.link_calls == 0  # 선택이 있으면 질문 매칭을 건너뜀


def test_missing_retriever_raises(generate_spy) -> None:
    with pytest.raises(KeyError):
        collect(make_service(CONFIRMED, retrievers=[]), "삼전 실적")


# ---------------------------------------------------------------- 생성자
def test_duplicate_retriever_names_rejected() -> None:
    with pytest.raises(ValueError):
        make_service(NOT_FOUND, retrievers=[FakeRetriever(), FakeRetriever()])
