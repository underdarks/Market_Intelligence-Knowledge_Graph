from dataclasses import replace

import openai
import pytest
import pytest_asyncio
from openai import AsyncOpenAI

from market_intelligence_knowledge_graph.config.classifier import ClassifierSettings, get_classifier_settings
from market_intelligence_knowledge_graph.config.config import LLM_GATEWAY_API_KEY, LLM_GATEWAY_BASE_URL
from market_intelligence_knowledge_graph.rag.classification.llm_classifier import LlmQuestionClassifier, _FALLBACK
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import QuestionType

# 실행법:uv run pytest -q -m integration -v -rs rag/classfication/test_llm_classifier_integration.py

# integration: 기본 실행에서 빠짐 (addopts), -m integration으로만 실행 (실제 LLM 호출 = 비용 발생)
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# 유형을 고르게 섞되 정답(type)은 단언하지 않음 → 정확도는 골든셋 평가 담당
QUESTIONS = [
    "TSMC 공장 멈추면 누가 영향받아?",  # 회사 언급 + 공급망
    "마이크런 2분기 실적 요약해줘",  # 오타 회사명 (guess 경로)
    "삼전이랑 하닉 영업이익률 비교해줘",  # 별명 2개
    "PER이 뭐야?",  # 회사 언급 없음
    "오늘 점심 뭐 먹지?",  # 범위 밖
]


@pytest.fixture(scope="module")
def settings() -> ClassifierSettings:
    # .env가 없으면 이 환경에선 연동 불가 → skip (RuntimeError로 전체를 에러 처리하지 않음)
    try:
        return get_classifier_settings()
    except RuntimeError as e:
        pytest.skip(str(e))


@pytest_asyncio.fixture  # pytest-asyncio 1.x strict 모드: async 픽스처는 이 데코레이터 필수
async def client():
    if not LLM_GATEWAY_BASE_URL or not LLM_GATEWAY_API_KEY:
        pytest.skip("게이트웨이 환경변수 없음")

    # 모듈 전역 _client를 재사용하지 않고 테스트마다 생성:
    # pytest-asyncio는 테스트마다 이벤트 루프가 바뀌어서, 이전 루프에 묶인 커넥션 풀을 쓰면 "Event loop is closed" 발생
    c = AsyncOpenAI(base_url=LLM_GATEWAY_BASE_URL, api_key=LLM_GATEWAY_API_KEY)
    # 게이트웨이가 꺼져 있으면 실패가 아니라 skip (연동 대상이 없는 것은 코드 버그가 아님)
    try:
        await c.with_options(timeout=3, max_retries=0).models.list()  # 헬스체크는 빨리 포기
    except openai.OpenAIError as e:
        await c.close()
        pytest.skip(f"게이트웨이 연결 불가: {type(e).__name__}")
    yield c
    await c.close()


def make(client, settings: ClassifierSettings, **override) -> LlmQuestionClassifier:
    # 운영 설정(.env)을 기본으로 쓰고, 실패 경로 테스트에서만 일부 값을 덮어씀
    # replace: frozen dataclass를 바꾸지 않고, 일부 값만 바꾼 사본을 만듦
    s = replace(settings, **override)
    return LlmQuestionClassifier(client, model=s.model, timeout_seconds=s.timeout_seconds, max_retries=s.max_retries)


# ── 1. 계약: 실제 모델 출력이 strict 스키마로 파싱되고 도메인 불변식을 만족 ──
@pytest.mark.parametrize("question", QUESTIONS, ids=["supply_chain", "typo", "aliases", "no_company", "out_of_scope"])
async def test_실제_호출_결과가_계약을_만족한다(client, settings, question):
    result = await make(client, settings).classify(question)

    # 폴백이면 연동 실패 (별칭 없음, strict 스키마 거부, 파싱 실패 등) → WARNING 로그로 원인 확인
    assert result != _FALLBACK, "폴백 반환: 게이트웨이 로그와 WARNING 로그 확인"
    assert isinstance(result.type, QuestionType)
    assert 0.0 < result.confidence <= 1.0
    # surface는 질문 원문 그대로여야 함 (링커가 의존하는 계약)
    for m in result.mentions:
        assert m.surface in question, f"surface가 원문에 없음: {m.surface!r}"


async def test_같은_질문은_같은_유형(client, settings):
    # temperature=0 재현성: 골든셋 평가 결과를 믿을 수 있는지의 전제
    clf = make(client, settings)
    first = await clf.classify(QUESTIONS[0])
    second = await clf.classify(QUESTIONS[0])
    assert first.type == second.type


# ── 2. 실패 경로: 실제 SDK 예외가 폴백으로 이어지는지 ──
async def test_타임아웃이면_폴백(client, settings):
    # 1ms 타임아웃 + 재시도 0 → 실제 APITimeoutError 발생
    result = await make(client, settings, timeout_seconds=0.001, max_retries=0).classify(QUESTIONS[0])
    assert result == _FALLBACK


async def test_게이트웨이에_없는_모델이면_폴백(client, settings):
    # 게이트웨이 4xx → OpenAIError → 폴백
    result = await make(client, settings, model="mikg-does-not-exist", max_retries=0).classify(QUESTIONS[0])
    assert result == _FALLBACK
