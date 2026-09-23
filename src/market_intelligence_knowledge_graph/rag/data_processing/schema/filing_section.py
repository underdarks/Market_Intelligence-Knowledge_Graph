from pydantic import BaseModel


# filing_text 컬렉션에서 공시문서의 섹션 한개를 나타내는 스키마
class FilingSection(BaseModel):
    entity_id: str  # 예: "cik:0001046179" 또는 "dart:00126380"
    source: str  # "edgar" | "dart" — 청킹 단계에서 언어(nori/standard) 판별 기준
    section_id: str  # 예: "risk_factors"
    section_title: str  # 예: "Risk Factors" — 검색 대상 아님, 표시용
    text: str  # 청킹 대상 원문
