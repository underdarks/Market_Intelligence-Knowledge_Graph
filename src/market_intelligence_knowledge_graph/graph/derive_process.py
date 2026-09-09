from math import e
from neo4j import EagerResult, Record

from market_intelligence_knowledge_graph import db

# SupplyRelation의 process_type를 조회해서 Company -[:PERFORMS] -> Process 관계 만드는 쿼리
_DERIVE_PERFORMS_QUERY = """
MATCH (from:Company)-[:FROM]->(sup:SupplyRelation)-[:TO]->(performer:Company)
WHERE sup.process_type IS NOT NULL
MERGE (performer)-[:PERFORMS]->(p:Process {process_id:"process:"+ sup.process_type})
ON CREATE SET
  p.name = $sup.process_type,
  p.process_type=sup.process_type,
  p.confidence = "inferred",
  p.derived_from = "supply_relation"
ON MATCH SET
  p.last_seen_at = datetime()
RETURN p.process_id as process_id, p.process_type AS process_type
"""


def derive_performs_from_supply_relations() -> int:
    with db.session() as s:
        eager: EagerResult = s.execute_write(
            transaction_function=lambda tx: tx.run(query=_DERIVE_PERFORMS_QUERY).to_eager_result()
        )
        print(f"  신규 Process 노드: {eager.summary.counters.nodes_created}개")
        print(f"  신규 PERFORMS 관계: {eager.summary.counters.relationships_created}개")
        records = eager.records
        for r in records:
            print(f"  [PERFORMS] {r['process_id']}")
        return len(records)
