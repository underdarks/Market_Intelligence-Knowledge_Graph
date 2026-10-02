import asyncio
import logging

import pytest

from market_intelligence_knowledge_graph.config.entity_linking import (
    get_entity_linking_settings,
)
from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import (
    AliasIndex,
    CompanyRecord,
    build_alias_index,
)
from market_intelligence_knowledge_graph.rag.entity_linking.company_index_loader import (
    load_company_records,
)
from market_intelligence_knowledge_graph.rag.entity_linking.matcher import match

# 모듈 전체 테스트에 integration 마커 적용 (함수마다 데코레이터 안 붙여도 됨)
pytestmark = pytest.mark.integration

# (질문, 기대 status). 픽스처 전용 케이스(현대차증권 등)는 실데이터에 없어서 제외
CASES: list[tuple[str, str]] = [
    ("삼전 리스크 뭐야", "confirmed"),
    ("삼성전기 환율 위험", "confirmed"),
    ("SK 하이닉스 HBM", "confirmed"),
    ("NVDA revenue", "confirmed"),
    ("NVDA실적 어때", "confirmed"),
    ("Broadcom Inc. risk factors", "confirmed"),
    ("community summary", "not_found"),
    ("삼성 리스크", "not_found"),
    ("반도체 리스크", "not_found"),
    ("삼성전자랑 삼성전기 비교", "multiple"),
]

"""실제 Neo4j 데이터로 링킹 케이스표를 검증하는 통합 테스트 (C1-7 검증, C1-14 재사용). 
실행: uv run pytest -m integration -q
"""


@pytest.fixture(
    scope="module"
)  # 모듈 안 테스트 전체가 Neo4j 조회 결과 1개를 공유 (케이스마다 조회 X)
def records() -> list[CompanyRecord]:
    async def _load() -> list[CompanyRecord]:
        try:
            return load_company_records()
        except Exception as e:
            print(e)

    # 동기 픽스처에서 async 함수 실행 (pytest-asyncio 없이도 동작)
    return asyncio.run(_load())


@pytest.fixture(scope="module")
def index(records: list[CompanyRecord]) -> AliasIndex:
    settings = get_entity_linking_settings()
    return build_alias_index(records, min_alphanum_len=settings.min_alphanum_len)


def test_companies_loaded(records: list[CompanyRecord]) -> None:
    # 0건이면 이후 케이스가 전부 not_found로 떨어져 원인 파악이 어려우므로 먼저 확인
    assert records, "Company 노드가 0건: Neo4j 연결 또는 적재 상태 확인"


def test_no_alias_conflicts(
    records: list[CompanyRecord], caplog: pytest.LogCaptureFixture
) -> None:
    # caplog은 함수 단위 픽스처라 모듈 픽스처(index)의 로그는 못 잡음 -> 여기서 한 번 더 빌드
    settings = get_entity_linking_settings()
    with caplog.at_level(logging.WARNING):  # 이 블록 안의 WARNING 이상 로그를 수집
        build_alias_index(records, min_alphanum_len=settings.min_alphanum_len)

    conflicts = [
        r.getMessage() for r in caplog.records if "별칭 충돌" in r.getMessage()
    ]
    assert not conflicts, f"별칭 충돌 발생: {conflicts}"


# parametrize: CASES 한 줄마다 별도 테스트로 실행. 실패해도 나머지 케이스는 계속 돔
# ids: 테스트 이름에 질문 문자열이 찍혀서 어느 케이스가 실패했는지 바로 보임
@pytest.mark.parametrize(("question", "expected"), CASES, ids=[q for q, _ in CASES])
def test_linking_cases(index: AliasIndex, question: str, expected: str) -> None:
    result = match(index, question)
    # 실패 메시지에 매칭된 회사와 걸린 별칭을 같이 출력: 시드 문제인지 matcher 문제인지 바로 구분
    found = [f"{e.name}({e.matched_alias})" for e in result.entities]
    assert (
        result.status.value == expected
    ), f"기대={expected}, 실제={result.status.value}, 매칭={found}"
