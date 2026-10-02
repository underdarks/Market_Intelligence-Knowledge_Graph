"""/ask 스트리밍 테스트. 실제 main 앱 대신 최소 앱을 조립해서 lifespan(Neo4j 로딩) 없이 검증."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from market_intelligence_knowledge_graph.api.dependencies import get_rag_service
from market_intelligence_knowledge_graph.api.middleware import RequestIdMiddleware
from market_intelligence_knowledge_graph.api.routes.ask_router import ask_router
from market_intelligence_knowledge_graph.api.sse import to_sse
from market_intelligence_knowledge_graph.config.api import get_api_settings
from market_intelligence_knowledge_graph.rag.schemas.answer_event import (
    ClarificationEvent,
    ClarifyReason,
    DoneEvent,
    TokenEvent,
)


class FakeService:
    """정해둔 이벤트를 내보내고, 옵션이면 중간에 예외."""

    def __init__(self, events: list, fail_after: bool = False) -> None:
        self._events = events
        self._fail_after = fail_after
        self.received = None  # 받은 AnswerRequest 기록

    async def response_answer_stream(self, req):
        self.received = req
        for event in self._events:
            yield event
        if self._fail_after:
            raise RuntimeError("내부 오류: DB 비밀번호 틀림")  # 외부로 새면 안 되는 메시지


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASK_QUESTION_MAX_LENGTH", "20")
    get_api_settings.cache_clear()  # lru_cache 비우기: 바꾼 환경변수를 다시 읽게
    yield
    get_api_settings.cache_clear()


def make_client(service: FakeService) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.include_router(ask_router)
    app.dependency_overrides[get_rag_service] = lambda: service  # 의존성을 가짜로 교체
    return TestClient(app)  # with 없이 생성: lifespan 미실행


def post_stream(client: TestClient, payload: dict, headers: dict | None = None):
    with client.stream("POST", "/ask", json=payload, headers=headers or {}) as response:
        return response, "".join(response.iter_text())


# ---- SSE 변환 ----
def test_to_sse_done() -> None:
    assert to_sse(DoneEvent()) == "event: done\ndata: {}\n\n"


def test_to_sse_keeps_korean_and_single_line() -> None:
    frame = to_sse(TokenEvent(text="삼성\n전자"))
    assert "삼성" in frame  # 한글 그대로
    assert frame.count("\n") == 3  # event줄 + data줄 + 빈 줄: 본문 줄바꿈은 이스케이프됨


# ---- 정상 스트림 ----
def test_stream_frames_in_order() -> None:
    service = FakeService(
        [
            ClarificationEvent(reason=ClarifyReason.NOT_FOUND, message="회사명을 넣어 주세요", candidates=[]),
            DoneEvent(),
        ]
    )
    response, body = post_stream(make_client(service), {"question": "반도체 리스크"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert body.index("event: clarification") < body.index("event: done")


def test_request_converted_to_answer_request() -> None:
    service = FakeService([DoneEvent()])
    post_stream(make_client(service), {"question": " 삼전 실적 ", "selected_entity_ids": ["dart:1"]})

    assert service.received.question == "삼전 실적"  # 공백 제거
    assert service.received.selected_entity_ids == ("dart:1",)  # list -> tuple 변환


# ---- 에러 ----
def test_error_event_ends_stream_without_leaking() -> None:
    service = FakeService([TokenEvent(text="부분 답변")], fail_after=True)
    response, body = post_stream(make_client(service), {"question": "삼전 실적"})

    assert body.rstrip().splitlines()[-2] == "event: error"  # 마지막 프레임이 error
    assert "event: done" not in body  # 에러 후 done 안 보냄
    assert "비밀번호" not in body  # 내부 예외 메시지 미노출
    assert response.headers["x-request-id"] in body  # 사용자가 문의할 키 포함


# ---- 검증 (422) ----
@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},  # 공백만
        {"question": "가" * 21},  # 길이 초과 (테스트 상한 20)
        {"question": "삼전", "unknown": 1},  # 모르는 필드
    ],
    ids=["blank", "too_long", "extra_field"],
)
def test_invalid_request_422(payload: dict) -> None:
    client = make_client(FakeService([DoneEvent()]))
    assert client.post("/ask", json=payload).status_code == 422


# ---- request_id ----
def test_request_id_echoed_when_given() -> None:
    response, _ = post_stream(make_client(FakeService([DoneEvent()])), {"question": "삼전"}, {"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"
