from neo4j import Record

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProcessCapability

# (Company)-[:PERFORMS]->(p:Product) 관계 생성
_MERGE_PERFORMS_QUERY = """
MATCH (c:Company {entity_id:$entity_id})
MERGE (p:Process {process_id:$process_id})
ON CREATE SET
  p.name = $name,
  p.process_type = $process_type
ON MATCH SET
  p.last_seen_at = datetime()
MERGE (c)-[pf:PERFORMS]->(p)
ON CREATE SET 
  pf.quoted_text=$quoted_text,
  pf.accession=$accession,
  pf.form=$form,
  pf.as_of_date=$as_of_date,
  pf.confidence = $confidence,
  pf.derived_from = $derived_from
ON MATCH SET
  pf.last_seen_at = datetime()
RETURN c.name AS company_name, p.name AS process_name, pf.confidence AS confidence
"""


# product, company-[:PERFORMS] -> product 관계 생성
def load_process_performs(entity_id: str, process_capability: ProcessCapability):
    if not all((entity_id, process_capability)):
        return None
    with db.session() as s:

        process_id = f"process:{process_capability.process_type}"

        params = {
            "entity_id": entity_id,
            "process_id": process_id,
            "name": process_capability.process_name,
            "process_type": process_capability.process_type,
            "quoted_text": process_capability.quoted_text,
            "accession": process_capability.accession,
            "form": process_capability.form,
            "as_of_date": process_capability.file_date,
            "confidence": process_capability.confidence,
            "derived_from": process_capability.derived_from,
        }

        r: Record | None = s.execute_write(lambda tx: tx.run(query=_MERGE_PERFORMS_QUERY, **params).single())
        print(f"  [MERGE] {r['company_name']} -PERFORMS-> {r['process_name']} ({r['confidence']})")
