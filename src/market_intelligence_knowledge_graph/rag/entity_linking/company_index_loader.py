import logging
from market_intelligence_knowledge_graph.config.neo4j_db import session
from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import CompanyRecord

log = logging.getLogger(__name__)

# 필요한 프로퍼티만 반환 (노드 통째로 반환하면 불필요한 데이터까지 전송됨)
# AS 뒤 이름은 CompanyRecord 필드명에 맞춤. 왼쪽 c.xxx는 keys(c)로 확인한 실제 프로퍼티명으로 교체
_COMPANY_QUERY = """
MATCH (c:Company)
RETURN c.entity_id    AS entity_id,
       c.name         AS name,
       c.aliases      AS aliases,
       c.tickers      AS tickers,
       c.former_names AS former_names
ORDER BY c.entity_id
"""
# ORDER BY: 반환 순서를 고정해서 기동할 때마다 인덱스가 같게 만들려는 것


def _to_tuple(value) -> tuple[str, ...]:
    """Neo4j 리스트 프로퍼티 -> tuple. 프로퍼티가 없으면 None이 오므로 빈 tuple로."""
    if value is None:
        return ()
    return tuple(value)


def to_company_record(row: dict) -> CompanyRecord:
    """Neo4j 결과 1행 -> CompanyRecord. DB 없이 테스트할 수 있게 순수 함수로 분리."""
    entity_id = row.get("entity_id")
    name = row.get("name")
    if not entity_id or not name:
        # 둘 중 하나라도 없으면 인덱스·되묻기 화면이 깨지므로 조용히 넘기지 않는다
        raise ValueError(f"entity_id 또는 name이 비어 있는 Company 노드: {row!r}")

    return CompanyRecord(
        entity_id=entity_id,
        name=name,
        aliases=_to_tuple(row.get("aliases")),
        tickers=_to_tuple(row.get("tickers")),
        former_names=_to_tuple(row.get("former_names")),
    )


# Neo4j에서 Company 노드 조회
def load_company_records() -> list[CompanyRecord]:
    with session() as s:
        result = s.run(_COMPANY_QUERY)
        rows = result.data()  # 결과 전체를 dict 리스트로 받음

    records: list[CompanyRecord] = [to_company_record(row) for row in rows]
    if not records:
        log.warning(
            "Company 노드가 0건입니다: 링킹이 항상 not_found가 됩니다"
        )  # 0건이면 링커가 항상 not_found를 내는 상태. 기동은 하되 원인 파악용으로 경고
    log.info("Company 로드 완료: %d건", len(records))
    return records
