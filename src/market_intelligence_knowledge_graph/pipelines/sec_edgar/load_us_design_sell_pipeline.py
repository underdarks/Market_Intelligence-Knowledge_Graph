import time

from edgar import Filing, set_identity

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.config import SEC_IDENTITY, SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.extraction.sec_edgar.judge_product import judge_products
from market_intelligence_knowledge_graph.extraction.sec_edgar.sec_edgar_text_extraction import (
    get_business_section,
    get_original_10K,
)
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProductJudgement
from market_intelligence_knowledge_graph.graph.load_company_products import load_company_product_relation
from market_intelligence_knowledge_graph.utils.entity import to_entity_id
from market_intelligence_knowledge_graph.sample.targets import TARGET_TICKERS

set_identity(SEC_IDENTITY)


# SEC EDGAR 기반 (Company)-[d:DESIGNS|SELLS]->(Product) 적재 파이프라인
def main():
    db.verify()

    for ticker in TARGET_TICKERS:
        try:
            # 1. 10-K에서 Item 1. Business (사업 내용) 추출
            original_10K: Filing | None = get_original_10K(ticker=ticker)
            if original_10K is None:
                print(f"[SKIP] {ticker}: 원본 10-K 없음")
                continue

            business_section: str = get_business_section(original_10K)
            if not business_section:
                print(f"[SKIP] {ticker}: Business 섹션 비어있음")
                continue

            # 2. llm 호출하여 "제품 목록 + 각 제품의 역할(design/sell/both) + 근거 문장" 판정 받음
            product_judgement: ProductJudgement = judge_products(ticker, business_section, original_10K.filing_date)
            if not product_judgement.products:
                print(f"[SKIP] {ticker}: 추출된 제품 없음")
                continue

            # 3. neo4j 적재
            load_company_product_relation(entity_id=to_entity_id(ticker), product_judgement=product_judgement)
            print(f"[LOAD] {ticker}: {len(product_judgement.products)}개 제품 적재")

        except Exception as e:
            print(f"[ERR] {e}")
        finally:
            time.sleep(SEC_RATE_LIMIT_SLEEP)


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
