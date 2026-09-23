from pydantic import BaseModel


# opensearch filing_chunks 인덱스에 적재될 최종 문서 하나.chunk_text_ko/chunk_text_en/embedding)와 1:1로 대응해야 함.
class FilingChunkDocument(BaseModel):
    doc_id: str  # OpenSearch _id로 쓸 값 (예: "cik:0001046179:risk_factors:0")
    # 주의: _source 안에 색인되는 필드가 아니라 bulk 요청의 메타데이터 줄({"index": {"_id": ...}})에만 씀
    entity_id: str  # 예: "cik:0001046179"
    section_id: str  # 예: "risk_factors"
    section_title: str  # 예: "Risk Factors"
    chunk_text_ko: str | None = None  # DART(한국어) 청크일 때만 값 있음, EDGAR면 None
    chunk_text_en: str | None = None  # EDGAR(영어) 청크일 때만 값 있음, DART면 None
    embedding: list[float]  # 1536차원
