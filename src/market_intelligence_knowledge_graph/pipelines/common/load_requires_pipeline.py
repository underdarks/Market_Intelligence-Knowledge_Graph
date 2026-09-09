from time import sleep
import time

from edgar import set_identity

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.config import SEC_IDENTITY
from market_intelligence_knowledge_graph.graph.load_requires import load_requires
from market_intelligence_knowledge_graph.sample.targets import MANUAL_REQUIRES

set_identity(SEC_IDENTITY)


# 해당 파이프라인은 sec/dart에서 데이터를 가져올 수 없으므로 SEC API 호출 및 LLM 판정 없음(추후 뉴스나 검색 api 사용)
# product-[:REQUIRES]->process 관계 생성 파이프라인
def main():
    db.verify()

    for target in MANUAL_REQUIRES:
        try:
            # 1. neo4j 저장
            load_requires(params=target)
        except Exception:
            print(f"[SKIP] Product/Process 매칭 실패: {target['product_id']} -> {target['process_id']}")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
