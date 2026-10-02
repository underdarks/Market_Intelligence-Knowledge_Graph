from pydantic import BaseModel, ConfigDict


class RetrievedItem(BaseModel):
    """
    검색 결과 하나를 표현하는 공통 DTO.
    RetrievedItem 하나는 항상 한 출처의 원자 단위를 유지한다. 여러 DB 결과를 하나의 content로 합치지 않는다.
    """

    source_type: str  # "vector_search" (OpenSearch) | "graph_traversal" (Neo4j) 기타 등..
    doc_id: str  # OpenSearch 문서 ID. 예: "af1ccb67:45"
    entity_id: str  # 예: "cik:0001046179"
    section_title: str  # 예: "business", "risk_factors"
    content: str  # LLM이 읽을 텍스트. chunk_text_ko/en 중 값 있는 쪽
    score: float  # 점수


class RetrievalQuery(BaseModel):
    """모든 검색기가 받는 공통 입력.

    DB별 세부사항(OpenSearch의 lang_field, Neo4j의 Cypher 등)은 넣지 않는다.
    그건 각 검색기가 내부에서 알아서 처리한다.
    """

    model_config = ConfigDict(frozen=True)  # 여러 검색기에 동시에 넘기므로 불변으로

    question: str  # 사용자 질문 원문
    entity_id: str  # 링킹된 회사 ID (Fan-out 붙으면 entity_ids: tuple[str, ...]로 확장)
