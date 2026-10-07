"""SupplyChainImpactRetriever 통합 테스트 (실제 Neo4j 필요).

실행: uv run pytest -m integration -q tests/integration/test_supply_chain_impact_retriever.py
데이터 건수는 적재 상태에 따라 바뀌므로, 정확한 개수 대신 "계약"(형태·순서·제외 규칙)을 단언한다.
"""

import asyncio
import re
import pytest

from market_intelligence_knowledge_graph.config.neo4j_async_db import create_neo4j_async_driver
from market_intelligence_knowledge_graph.rag.retrieve.schema.schema import RetrievalQuery, RetrievedItem
from market_intelligence_knowledge_graph.rag.retrieve.supply_chain_impact_retriever import SupplyChainImpactRetriever

# create_async_driver: neo4j_db.py와 같은 폴더의 neo4j_async.py (경로 맞춰서)
TSMC_NAME = "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD"  # Neo4j Company.name 실제 표기

pytestmark = pytest.mark.integration  # 기본 pytest 실행에선 제외

TSMC = "cik:0001046179"  # Track B 검증 때 쓴 기준 회사 (위탁 관계·공정 데이터가 있음)
MAX_PATHS = 10


def retrieve(entity_id: str, max_paths: int = MAX_PATHS) -> list[RetrievedItem]:
    """드라이버 생성 -> 검색 -> 종료를 한 이벤트 루프 안에서 처리.

    비동기 드라이버는 생성된 루프에 묶이므로, asyncio.run마다 새로 만들어야 안전함
    """

    async def _run() -> list[RetrievedItem]:
        driver = create_neo4j_async_driver()
        try:
            retriever = SupplyChainImpactRetriever(driver=driver, max_paths=max_paths)
            return await retriever.retrieve(RetrievalQuery(question="TSMC 차질 영향", entity_id=entity_id))
        finally:
            await driver.close()  # 테스트가 실패해도 연결 반납

    return asyncio.run(_run())


@pytest.fixture(scope="module")
def tsmc_items() -> list[RetrievedItem]:
    """TSMC 결과를 모듈에서 1번만 조회해 여러 테스트가 공유 (결과 리스트는 루프와 무관해서 안전)."""
    return retrieve(TSMC)


# ---- 기본 계약 ----
def test_returns_results_for_tsmc(tsmc_items) -> None:
    assert tsmc_items, "TSMC 영향 경로가 0건: Track B 데이터 적재 상태 확인"


def test_all_items_are_graph_sources(tsmc_items) -> None:
    assert all(item.source_type == "graph_traversal" for item in tsmc_items)


def test_doc_ids_unique(tsmc_items) -> None:
    # 출처 번호마다 서로 다른 근거여야 함 (SELLS/DESIGNS 중복 버그 회귀 방지)
    doc_ids = [item.doc_id for item in tsmc_items]
    assert len(doc_ids) == len(set(doc_ids)), f"중복 doc_id: {doc_ids}"


def test_self_excluded(tsmc_items) -> None:
    # 기준 회사가 영향 회사로 나오면 안 됨
    assert all(item.entity_id != TSMC for item in tsmc_items)


def test_sorted_by_score_desc(tsmc_items) -> None:
    scores = [item.score for item in tsmc_items]
    assert scores == sorted(scores, reverse=True)


def test_max_paths_respected() -> None:
    assert len(retrieve(TSMC, max_paths=2)) <= 2


# ---- 경로별 ----
def test_supply_path_present_with_percent(tsmc_items) -> None:
    # 경로 B: SupplyRelation이 TSMC를 향하므로 위탁 관계 출처가 있어야 함
    supply_items = [item for item in tsmc_items if item.section_title == "공급망 영향: 위탁 관계"]
    assert supply_items, "위탁 관계 경로 0건"
    # 의존도는 비율이 아니라 퍼센트로 표기돼야 함 (0.95 -> 95%)
    assert all("%" in item.content or "미공개" in item.content for item in supply_items)


def test_content_mentions_source_company(tsmc_items) -> None:
    # 인용문 속 "TSMC"가 아니라, 문장 본문에 기준 회사명(Neo4j 표기)이 들어갔는지 확인
    assert all(TSMC_NAME in item.content for item in tsmc_items)


# ---- 경계 ----
def test_unknown_entity_returns_empty() -> None:
    # 없는 회사면 예외 없이 빈 리스트 (문서 검색만으로 답변이 진행되게)
    assert retrieve("cik:0000000000") == []


def test_derived_paths_excluded(tsmc_items) -> None:
    # E: 파생 PERFORMS(confidence null)를 거치는 경로는 쿼리에서 제외됨
    # -> 공정 경유 경로에 "미상" 신뢰도가 남아 있으면 제외 조건이 깨진 것
    process_items = [i for i in tsmc_items if i.section_title == "공급망 영향: 공정 경유"]
    assert all("미상" not in i.content for i in process_items)


def test_sells_and_designs_merged(tsmc_items) -> None:
    # A: 같은 회사가 같은 제품을 판매·설계 둘 다 하면 한 행으로 묶임
    # 현재 데이터(NVIDIA·AMD의 GPUs)에서 최소 1건은 묶인 문장이 나와야 함
    assert any("판매·설계함" in i.content for i in tsmc_items)


# 공시에서 의존 비중을 밝히는 표현들: 숫자(95%, 95 percent) 또는 수량 단어
# 휴리스틱이라 완벽하지 않음: 오탐·누락이 보이면 패턴을 추가
_QUANTITY_PATTERN = re.compile(
    r"\d+(\.\d+)?\s?%|\bpercent\b|\bsubstantially all\b|\ball (?:of )?(?:our )?wafers\b",
    re.IGNORECASE,  # 대소문자 무시
)


def test_disclosed_supply_cites_quantity(tsmc_items) -> None:
    # 데이터 품질 불변 조건: disclosed(수치 명시) 관계는 근거 문장에 수량 표현이 있어야 함
    # 정정 전 NVIDIA("such as TSMC and Samsung", 수량 없음) 같은 오판정이 다시 들어오면 여기서 잡힘
    supply_items = [i for i in tsmc_items if i.section_title == "공급망 영향: 위탁 관계"]
    for item in supply_items:
        if "관계 신뢰도: disclosed" in item.content:
            evidence = item.content.split("근거:")[-1]
            assert _QUANTITY_PATTERN.search(evidence), f"수량 표현 없는 disclosed 근거: {item.content}"
