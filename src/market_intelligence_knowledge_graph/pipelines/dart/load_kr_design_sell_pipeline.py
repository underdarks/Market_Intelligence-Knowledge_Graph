import time

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.config import DART_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.extraction.dart.dart_document import (
    get_business_report_rcept_no,
    get_document_text,
    get_product_section,
)
from market_intelligence_knowledge_graph.extraction.sec_edgar.judge_product import judge_products
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProductJudgement
from market_intelligence_knowledge_graph.graph.load_company_products import load_company_product_relation
from market_intelligence_knowledge_graph.sample.targets import TARGET_KR_COMPANYS
from market_intelligence_knowledge_graph.utils.entity import normalize_dart_date, to_entity_id


# Dart 기반 (Company)-[d:DESIGNS|SELLS]->(Product) 적재 파이프라인
def main():
    db.verify()

    for target in TARGET_KR_COMPANYS:
        try:
            corp_code = target["corp_code"]
            name = target["name"]

            # 1. 최신 사업 보고서 recpt_no 추출
            res: tuple[str, str] = get_business_report_rcept_no(corp_code=corp_code)
            if res is None:
                print(f"[SKIP] {name}: 사업보고서 없음")
                continue
            rcept_no, rcept_date = res

            # 2. 사업 보고서 원문 추출
            doc = get_document_text(rcept_no=rcept_no)
            if doc is None:
                print(f"[SKIP] {name}: 원문 다운로드 실패")
                continue

            product_section = get_product_section(xml_content=doc)
            if product_section is None:
                print(f"[SKIP] {name}: 제품 섹션 없음")
                continue

            # 3. llm 호출하여 "제품 목록 + 각 제품의 역할(design/sell/both) + 근거 문장" 판정 받음
            product_judgement: ProductJudgement = judge_products(
                ticker=corp_code, business_section=product_section, filling_date=normalize_dart_date(rcept_date)
            )
            if not product_judgement:
                print(f"[SKIP] {corp_code}: 추출된 제품 없음")
                continue

            # 4. neo4j 적재
            load_company_product_relation(
                entity_id=to_entity_id(id=corp_code, country="kr"), product_judgement=product_judgement
            )
            print(f"[LOAD] {name}: {len(product_judgement.products)}개 제품 적재")

        except Exception as e:
            print(f"[ERR] {target['name']}: {type(e).__name__} {e}")
        finally:
            time.sleep(DART_RATE_LIMIT_SLEEP)


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
