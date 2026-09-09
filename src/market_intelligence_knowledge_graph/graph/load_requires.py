# (Product) -[:REQUIRES] -> (Process) 관계 생성
from neo4j import Record

from market_intelligence_knowledge_graph import db

_MERGE_REQUIRES_QUERY = """
MATCH(prd:Product {product_id:$product_id})
MATCH(prc:Process {process_id:$process_id})
MERGE (prd)-[r:REQUIRES]->(prc)
ON CREATE SET
  r.confidence = $confidence,
  r.quoted_text = $quoted_text,
  r.source_url = $source_url,
  r.source_type = $source_type,
  r.as_of_date = $as_of_date,
  r.extraction_method = "manual"
ON MATCH SET
  r.last_seen_at = datetime()
RETURN prd.name AS product_name, prc.name AS process_name, r.confidence AS confidence
"""

# product-[:REQUIRES]->process 관계 생성
def load_requires(params: dict) -> None:
    with db.session() as s:
        r = s.execute_write(lambda tx: tx.run(_MERGE_REQUIRES_QUERY, **params).single())
        print(f"  [MERGE] {r['product_name']} -REQUIRES-> {r['process_name']} ({r['confidence']})")
