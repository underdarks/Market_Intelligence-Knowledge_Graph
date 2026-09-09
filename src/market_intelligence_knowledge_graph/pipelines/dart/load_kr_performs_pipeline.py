import time

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.config import DART_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.extraction.dart.dart_document import (
    get_business_report_rcept_no,
    get_document_text,
    get_product_section,
)
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProcessCapability
from market_intelligence_knowledge_graph.graph.load_process_capability import load_process_performs
from market_intelligence_knowledge_graph.sample.targets import MANUAL_PERFORMS_KR
from market_intelligence_knowledge_graph.utils.entity import normalize_dart_date, to_entity_id


# Dart기반 product, company-[:PERFORMS] -> product 파이프라인(현재는 수동 큐레이션, 추후 자동화)
def main():
    db.verify()

    for item in MANUAL_PERFORMS_KR:
        try:
            entity_id = to_entity_id(item["corp_code"], country="kr")
            process_capability = ProcessCapability(
                process_name=item["process_name"],
                process_type=item["process_type"],
                confidence=item["confidence"],
                derived_from=item["form"],
                quoted_text=item["quoted_text"],
                accession="",  # 뉴스라 accession 없음
                form=item["form"],
                file_date=item["as_of_date"],
            )

            load_process_performs(
                entity_id=entity_id,
                process_capability=process_capability,
            )
            print(f"[LOAD] {item['corp_code']} PERFORMS {item['process_name']}")
        except Exception as e:
            print(f"[ERR] {item['process_name']}: {type(e).__name__} {e}")
        finally:
            time.sleep(DART_RATE_LIMIT_SLEEP)


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
