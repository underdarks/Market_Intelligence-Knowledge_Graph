import hashlib

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import JudgedRelation

# SupplyRelation/Evidence 적재 로직

"""
1. Evidence는 SEC 공시가 이미 확정된 문서라 바뀌지 않음
2. SupplyRelation의 confidence 프로퍼티에 대해서 기존이 "stated"인데 새로 "disclosed"가 들어오면 갱신 (더 구체적인 정보로 업그레이드)
   그 반대(이미 disclosed인데 stated가 들어옴)면 기존 값을 그대로 유지 — 정보 후퇴 방지
"""

_MERGE_SUPPLY_RELATION_QUERY = """
MATCH (from:Company {entity_id:$from_entity_id})
MATCH (to:Company {entity_id:$to_entity_id})
MERGE (from)-[:FROM]->(sup:SupplyRelation {relation_id:$relation_id})
MERGE (sup)-[:TO]->(to)
ON CREATE SET 
    sup.confidence = $confidence,
    sup.dependency_pct = $dependency_pct,
    sup.process_type = $process_type,
    sup.as_of_date = $as_of_date
ON MATCH SET
    sup.confidence = CASE 
        WHEN sup.confidence = "stated" AND $confidence = "disclosed"
        THEN $confidence ELSE sup.confidence END,
    sup.dependency_pct = CASE
        WHEN sup.confidence = "stated" AND $confidence = "disclosed"
        THEN $dependency_pct ELSE sup.dependency_pct END,
    sup.as_of_date = CASE
        WHEN sup.confidence = "stated" AND $confidence = "disclosed"
        THEN $as_of_date ELSE sup.as_of_date END
                        
MERGE (sup)-[:SUPPORTED_BY]->(evi:Evidence {evidence_id:$evidence_id})
ON CREATE SET 
    evi.quoted_text = $quoted_text,
    evi.accession = $accession,
    evi.form = $form,
    evi.file_date = $file_date,
    evi.extraction_method = $extraction_method,
    evi.reasoning = $reasoning
ON MATCH SET 
    evi.last_seen_at = datetime(),
    evi.accession = $accession
RETURN sup.relation_id AS relation_id, evi.evidence_id AS evidence_id
"""


# tx:Neo4j 드라이버가 넘겨주는 트랜잭션 객체(사용자가 직접 BEGIN, COMMIT, ROLLBACK을 명령어로 제어하지 않고, 드라이버가 트랜잭션의 시작과 끝을 관리)
# "**params" : tx 외에 전달되는 모든 키워드 인자(Key=Value)들을 params라는 하나의 파이썬 딕셔너리(dict)로 묶어서(Packing) 받겠다는 뜻입니다.
def _merge_supplyrelation_evidence(tx, **params):
    return tx.run(_MERGE_SUPPLY_RELATION_QUERY, **params).single()


def _make_evidence_id(accession: str, matched_alias: str, quoted_text: str) -> str:
    # 문서(accession)와 키워드(matched_alias)가 같아도 문단 내용이 다르면 서로 다른 evidence_id가 되도록 문단 텍스트의 해시를 추가
    # 예: 같은 AVGO 10-K, 같은 "TSMC" 키워드로 찾은 문단 6개가 전부 다른 evidence_id를 갖게 됨 (텍스트가 다르니까)
    text_hash = hashlib.md5(quoted_text.encode()).hexdigest()[:8]
    return f"{accession}:{matched_alias}:{text_hash}"


# SupplyRelation/Evidence 적재 메서드
def load_supply_relation(judgedRelation: JudgedRelation):
    # relation_id 규칙 : 위탁하는회사 -> 위탁받는회사:어떤공정인지
    relation_id = (
        f"{judgedRelation.from_entity_id}->{judgedRelation.to_entity_id}:{judgedRelation.relation.process_type}"
    )
    evidence_id = _make_evidence_id(
        accession=judgedRelation.evidence.accession,
        matched_alias=judgedRelation.evidence.matched_alias,
        quoted_text=judgedRelation.evidence.quoted_text,
    )

    params = {
        "from_entity_id": judgedRelation.from_entity_id,
        "to_entity_id": judgedRelation.to_entity_id,
        "relation_id": relation_id,
        "confidence": judgedRelation.relation.confidence,
        "dependency_pct": judgedRelation.relation.dependency_pct,
        "process_type": judgedRelation.relation.process_type,
        "as_of_date": judgedRelation.relation.as_of_date,
        "evidence_id": evidence_id,
        "quoted_text": judgedRelation.evidence.quoted_text,
        "form": judgedRelation.evidence.form,
        "file_date": judgedRelation.evidence.file_date,
        "extraction_method": judgedRelation.evidence.extraction_method,
        "reasoning": judgedRelation.evidence.reasoning,
        "accession": judgedRelation.evidence.accession,
    }

    with db.session() as s:
        record = s.execute_write(transaction_function=_merge_supplyrelation_evidence, **params)
        print(
            f"  [MERGE] {judgedRelation.from_ticker} -> {judgedRelation.to_ticker} "
            f"({judgedRelation.relation.confidence}, {judgedRelation.relation.process_type}) "
            f"relation={record['relation_id']} evidence={record['evidence_id']}"
        )
