from pydantic import BaseModel


class RetrievedItem(BaseModel):
    """
    검색 결과 하나를 표현하는 공통 DTO.
    RetrievedItem 하나는 항상 한 출처의 원자 단위를 유지한다. 여러 DB 결과를 하나의 content로 합치지 않는다.
    """

    source_type: str  # "vector_search" (OpenSearch) | "graph_traversal" (Neo4j)
    doc_id: str  # OpenSearch 문서 ID. 예: "af1ccb67:45"
    entity_id: str  # 예: "cik:0001046179"
    section_title: str  # 예: "business", "risk_factors"
    content: str  # LLM이 읽을 텍스트. chunk_text_ko/en 중 값 있는 쪽
    score: float  # 점수
