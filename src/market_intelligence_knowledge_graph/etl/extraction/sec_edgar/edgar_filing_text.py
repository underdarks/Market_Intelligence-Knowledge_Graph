from edgar import Company, Filing, set_identity

from market_intelligence_knowledge_graph.config.config import SEC_IDENTITY
from market_intelligence_knowledge_graph.etl.extraction.common.schemas.schema_filling_text import FilingTextBronzeDoc
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_text_extraction import (
    get_original_10K,
    get_original_20F,
)

set_identity(SEC_IDENTITY)

""" EDGAR 10-K/20-F 본문(business/risk_factors/management_discussion)을 FilingTextBronzeDoc으로 추출하는 모듈 """


# EDGAR 10-K(없으면 20-F) 최신 원본에서 3개 섹션을 FilingTextBronzeDoc 리스트로 변환
def parse_edgar_document(
    ticker: str,
    entity_id: str,
) -> list[FilingTextBronzeDoc]:
    # 10-K 우선, 없으면(TSM 등 외국 발행인) 20-F로 폴백
    filing: Filing | None = get_original_10K(ticker)
    doc_type = "10-K"
    if filing is None:
        filing = get_original_20F(ticker)
        doc_type = "20-F"

    if filing is None:
        print(f"[SKIP] {ticker}: 10-K/20-F 둘 다 없음")
        return []

    obj = filing.obj()

    sections = {
        "business": obj.business,
        "risk_factors": obj.risk_factors,
        "management_discussion": obj.management_discussion,
    }

    docs: list[FilingTextBronzeDoc] = []
    for section_id, text in sections.items():
        text = (text or "").strip()
        if not text:
            print(f"[SKIP] {ticker}: {section_id} 섹션 비어있음")
            continue

        docs.append(
            FilingTextBronzeDoc(
                entity_id=entity_id,
                source="edgar",
                doc_type=doc_type,
                accession_no=filing.accession_no,
                section_id=section_id,
                section_title=section_id,  # edgartools가 원문 제목을 별도로 안 줘서 section_id로 대체
                section_title_en=None,
                text=text,
                fiscal_year=filing.filing_date.year,
                filed_date=str(filing.filing_date),
            )
        )

    return docs
