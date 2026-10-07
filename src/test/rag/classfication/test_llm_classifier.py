import logging
from types import SimpleNamespace
from unittest.mock import Mock

import openai
import pytest

from market_intelligence_knowledge_graph.rag.classification.llm_classifier import (
    LlmQuestionClassifier,
    _ClassifierOutput,
    _MentionOutput,
    _FALLBACK,
)
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import ExtractedMention, QuestionType

# 모듈 안 모든 테스트가 async → 파일 단위로 asyncio 마크 (asyncio_mode 설정과 무관하게 동작)
pytestmark = pytest.mark.asyncio


# ── 가짜 클라이언트 ─────────────────────────────────────────────
class FakeCompletions:
    """chat.completions.parse 대역: 호출 인자를 기록하고, 정해둔 응답을 주거나 예외를 던진다."""

    def __init__(self, *, parsed=None, refusal=None, error: Exception | None = None):
        self._parsed, self._refusal, self._error = parsed, refusal, error
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        # 실제 SDK 응답 구조 흉내: completion.choices[0].message.parsed / .refusal
        message = SimpleNamespace(parsed=self._parsed, refusal=self._refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """AsyncOpenAI 대역: with_options는 받은 옵션을 기록하고 자기 자신을 반환."""

    def __init__(self, completions: FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)
        self.options: dict = {}

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


# ── 헬퍼 ──────────────────────────────────────────────────────
def make(completions: FakeCompletions) -> tuple[LlmQuestionClassifier, FakeClient]:
    client = FakeClient(completions)
    clf = LlmQuestionClassifier(client, model="mikg-classify", timeout_seconds=5, max_retries=1)
    return clf, client


def output(qtype=QuestionType.T3, confidence=0.9, mentions=(("TSMC", None),), reason="공급망 영향 질문"):
    # model_construct: 검증을 건너뛰고 객체 생성 → "LLM이 범위 밖 값을 준 상황"을 재현할 수 있음
    return _ClassifierOutput.model_construct(
        type=qtype,
        confidence=confidence,
        reason=reason,
        mentions=[_MentionOutput.model_construct(surface=s, guess=g) for s, g in mentions],
    )


def sdk_error(cls):
    # SDK 버전마다 httpx Request 타입이 달라서 더미 request로 생성
    return cls(request=Mock())


def warned(caplog) -> bool:
    # 로그 문구가 바뀌어도 깨지지 않게 WARNING 레코드 존재만 확인
    return any(r.levelno == logging.WARNING for r in caplog.records)


# ── 1. 정상 ───────────────────────────────────────────────────
async def test_정상_분류_결과를_Classification으로_반환():
    clf, _ = make(FakeCompletions(parsed=output()))

    result = await clf.classify("TSMC 공장 멈추면 누가 영향받아?")

    assert result.type == QuestionType.T3
    assert result.confidence == 0.9
    assert result.mentions == (ExtractedMention(surface="TSMC", guess=None),)


async def test_요청에_모델_질문_출력스키마_옵션이_전달된다():
    completions = FakeCompletions(parsed=output())
    clf, client = make(completions)

    await clf.classify("질문")

    call = completions.calls[0]
    assert call["model"] == "mikg-classify"
    assert call["response_format"] is _ClassifierOutput
    assert call["temperature"] == 0
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][-1] == {"role": "user", "content": "질문"}
    assert client.options == {"timeout": 5, "max_retries": 1}


async def test_reason은_로그에만_남고_결과에는_없다(caplog):
    clf, _ = make(FakeCompletions(parsed=output(reason="공급망 영향 질문")))

    with caplog.at_level(logging.INFO):
        result = await clf.classify("질문")

    assert "공급망 영향 질문" in caplog.text
    assert "reason" not in type(result).model_fields  # Classification 필드에 reason 없음


# ── 2. 거부 ───────────────────────────────────────────────────
async def test_모델_거부시_폴백(caplog):
    clf, _ = make(FakeCompletions(parsed=None, refusal="I can't help with that"))

    with caplog.at_level(logging.WARNING):
        result = await clf.classify("질문")

    assert result == _FALLBACK
    assert warned(caplog)


# ── 3. SDK 오류 ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "error",
    [
        sdk_error(openai.APITimeoutError),
        sdk_error(openai.APIConnectionError),
    ],
    ids=["timeout", "connection"],
)
async def test_SDK_오류시_폴백(error, caplog):
    clf, _ = make(FakeCompletions(error=error))

    with caplog.at_level(logging.WARNING):
        result = await clf.classify("질문")

    assert result == _FALLBACK
    assert warned(caplog)


# ── 4. 신뢰도 범위 ────────────────────────────────────────────
@pytest.mark.parametrize("confidence", [-0.1, 1.01, 7.0])
async def test_신뢰도_범위_위반시_폴백(confidence, caplog):
    clf, _ = make(FakeCompletions(parsed=output(confidence=confidence)))

    with caplog.at_level(logging.WARNING):
        result = await clf.classify("질문")

    assert result == _FALLBACK
    assert warned(caplog)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
async def test_신뢰도_경계값은_허용(confidence):
    clf, _ = make(FakeCompletions(parsed=output(confidence=confidence)))

    result = await clf.classify("질문")

    assert result.confidence == confidence


# ── 5. 언급 매핑 (1:1) ────────────────────────────────────────
async def test_언급은_surface_guess_그대로_순서대로_매핑된다():
    clf, _ = make(FakeCompletions(parsed=output(mentions=(("마이크런", "마이크론"), ("TSMC", None)))))

    result = await clf.classify("마이크런이랑 TSMC 관계는?")

    assert result.mentions == (
        ExtractedMention(surface="마이크런", guess="마이크론"),
        ExtractedMention(surface="TSMC", guess=None),
    )


async def test_언급_없음은_빈_튜플():
    clf, _ = make(FakeCompletions(parsed=output(mentions=())))

    result = await clf.classify("PER이 뭐야?")

    assert result.mentions == ()
