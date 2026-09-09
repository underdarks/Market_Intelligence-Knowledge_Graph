from neo4j import Record

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProductInfo, ProductJudgement

_MERGE_DESIGNS_QUERY = """
MATCH (c:Company {entity_id: $entity_id})
MERGE (p:Product {product_id: $product_id})
ON CREATE SET 
  p.name = $name,
  p.category = $category
ON MATCH SET
  p.last_seen_at = datetime()
MERGE (c)-[d:DESIGNS]->(p)
ON CREATE SET
  d.quoted_text = $quoted_text,
  d.confidence = $confidence,
  d.as_of_date = $as_of_date
ON MATCH SET
  p.last_seen_at = datetime()
RETURN
    c.name AS company_name,
    p.product_id AS product_id,
    p.name AS product_name,
    type(d) AS relation_type,
    d.confidence AS confidence
"""


_MERGE_SELLS_QUERY = """
MATCH (c:Company {entity_id: $entity_id})
MERGE (p:Product {product_id: $product_id})
ON CREATE SET 
  p.name = $name,
  p.category = $category
ON MATCH SET
  p.last_seen_at = datetime()
MERGE (c)-[d:SELLS]->(p)
ON CREATE SET
  d.quoted_text = $quoted_text,
  d.confidence = $confidence,
  d.as_of_date = $as_of_date
ON MATCH SET
  p.last_seen_at = datetime()
RETURN
  c.name AS company_name,
  p.product_id AS product_id,
  p.name AS product_name,
  type(d) AS relation_type,
  d.confidence AS confidence
"""


def _normalize_product_id(name: str) -> str:
    return f"product:{name.lower().replace(" ", "_")}"


def _merge_tx(tx, query: str, **params):
    """
    tx.run시 neo4j로 실제 네트워크 i/o 발생
    1. 파이썬 드라이버가 Cypher 쿼리 문자열 + 파라미터를 Bolt 프로토콜(Neo4j 전용 바이너리 프로토콜, TCP 위에서 동작)로 직렬화
    2. 세션이 물고 있는 TCP 커넥션을 통해 서버로 전송
    3. 서버가 쿼리를 파싱·실행하고, 결과를 다시 Bolt 프로토콜로 응답
    4. 드라이버가 그 응답을 받아서 Result 객체로 파이썬에 넘겨줌
    """

    return tx.run(query, **params).single()  # tx.run시 neo4j로 실제 네트워크 i/o 발생


# (Company)-[d:DESIGNS|SELLS]->(Product) 관계 생성
def load_company_product_relation(entity_id: str, product_judgement: ProductJudgement) -> None:
    with db.session() as s:
        for product in product_judgement.products:

            # 빈 문자 혹은 None타입 체크(text == null || text.isEmpty())
            if not product.name or not product.category:
                print(f"  [SKIP] 불완전한 제품 정보: {product}")
                continue

            params = {
                "product_id": _normalize_product_id(product.name),
                "name": product.name,
                "entity_id": entity_id,
                "category": product.category,
                "quoted_text": product.quoted_text,
                "confidence": product.confidence,
                "as_of_date": product.as_of_date,
            }

            # print(f"param={params}")

            if product.role in ("designs", "both"):
                r: Record | None = s.execute_write(lambda tx: _merge_tx(tx, query=_MERGE_DESIGNS_QUERY, **params))
                print(
                    f"  [MERGE] {r['company_name']} - [:{r['relation_type']}]-> {r['product_name']} ({r['confidence']})"
                )

            if product.role in ("sells", "both"):
                r = s.execute_write(lambda tx: _merge_tx(tx, query=_MERGE_SELLS_QUERY, **params))
                print(
                    f"  [MERGE] {r['company_name']} - [:{r['relation_type']}]-> {r['product_name']} ({r['confidence']})"
                )
