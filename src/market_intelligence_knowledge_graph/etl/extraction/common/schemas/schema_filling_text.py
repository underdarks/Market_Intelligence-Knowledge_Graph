from pydantic import BaseModel, ConfigDict, Field
from bson import ObjectId


# DART/EDGAR 공시 본문(business/risk_factors/management_discussion)을 저장하기 위한 공통 스키마.
class FilingTextBronzeDoc(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # 삽입 전(막 생성된 시점)엔 None, DB에서 읽어올 때는 MongoDB가 채워준 값
    # (financials 스키마 때와 동일한 이유로 Optional)
    id: ObjectId | None = Field(default=None, alias="_id")

    entity_id: str  # "cik:0001730168" / "dart:00126371"
    source: str  # "edgar" | "dart"
    doc_type: str  # "10-K"/"20-F" (EDGAR) 또는 "사업보고서"(DART)

    accession_no: str | None = None  # EDGAR 전용
    rcept_no: str | None = None  # DART 전용

    section_id: str  # "business" | "risk_factors" | "management_discussion"
    # 소스 무관 공통 — 쿼리할 때 source 안 가리고 검색 가능

    section_title: str  # 원문 제목 그대로
    # (DART risk_factors 2건은 이 필드로 구분됨:
    #  "위험관리 및 파생거래" vs "우발부채 등에 관한사항")
    section_title_en: str | None = None
    # DART는 XML의 ENG 속성에서 무료로 확보
    # EDGAR는 별도 영문 제목이 따로 없어 None

    text: str  # 본문 (표는 마크다운으로 변환되어 포함됨)

    fiscal_year: int
    filed_date: str  # DART는 근사치(rcept_no 앞 8자리), EDGAR는 filing_date
    url: str | None = None  # 아직 안 채움 (필요시 나중에 추가)
