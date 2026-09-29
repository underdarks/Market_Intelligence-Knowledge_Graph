# EDGAR/DART 공시 본문(filing_text)을 13개사 전체 수집해서 적재하는 파이프라인.


import time

from market_intelligence_knowledge_graph.config.config import DART_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.config.mongo_db import close, verify
from market_intelligence_knowledge_graph.etl.extraction.dart.dart_filing_text import (
    find_annual_report_rcept_no,
    parse_dart_document,
)
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_filing_text import parse_edgar_document
from market_intelligence_knowledge_graph.etl.load.mongo.load_filing_text import load_filing_text_documents
from market_intelligence_knowledge_graph.sample.targets import TARGET_KR_COMPANYS, TARGET_US_COMPANYS
from market_intelligence_knowledge_graph.utils.utils import to_entity_id


# dart, edgar 공시 본문(filing_text)를  수집,적재하는 파이프라인
def main():
    verify()
    total_count = 0

    # SEC EDGAR
    for ticker in TARGET_US_COMPANYS:
        entity_id = to_entity_id(id=ticker, country="us")
        try:
            # 1. 공시 본문 추출
            docs = parse_edgar_document(ticker=ticker, entity_id=entity_id)

            # 2. mongodb 적재
            count = load_filing_text_documents(docs)
            total_count += count
            print(f"[LOAD] {ticker}: {count}건 적재")
        except Exception as e:
            print(f"[ERR] {ticker}: {type(e).__name__} {e}")

    # DART
    for target in TARGET_KR_COMPANYS:
        corp_code = target["corp_code"]
        name = target["name"]
        entity_id = to_entity_id(id=corp_code, country="kr")
        try:
            rcept_no = find_annual_report_rcept_no(corp_code=corp_code)
            docs = parse_dart_document(
                rcept_no=rcept_no,
                entity_id=entity_id,
                doc_type="사업보고서",
                fiscal_year=int(rcept_no[:4]),  # rcept_no 앞 4자리가 접수연도(근사치)
                filed_date=rcept_no[:8],  # YYYYMMDD 근사치
            )
            count = load_filing_text_documents(docs)
            total_count += count
            print(f"[LOAD] {name}: {count}건 적재")
        except Exception as e:
            print(f"[ERR] {name}: {type(e).__name__} {e}")
        finally:
            time.sleep(DART_RATE_LIMIT_SLEEP)

    print(f"filing_text 전체 적재 완료: 총 {total_count}건")


if __name__ == "__main__":
    try:
        main()
    finally:
        close()
