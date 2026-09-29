from datetime import datetime
import time

from market_intelligence_knowledge_graph.config.config import DART_RATE_LIMIT_SLEEP, SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.config.mongo_db import close, verify
from market_intelligence_knowledge_graph.etl.extraction.dart.dart_financials import get_dart_financials
from market_intelligence_knowledge_graph.etl.load.mongo.load_financials_raw import load_dart_financials
from market_intelligence_knowledge_graph.sample.targets import TARGET_KR_COMPANYS

CURRENT_YEAR = datetime.now().year
YEARS_BACK = 5


# DART 기업 재무재표 적재 파이프라인
def main():
    verify()

    for target in TARGET_KR_COMPANYS:
        name = target["name"]
        total_count = 0

        for year_offset in range(YEARS_BACK):
            bsns_year = str(CURRENT_YEAR - year_offset)  # 사업연도
            try:
                financials = get_dart_financials(corp_code=target["corp_code"], bsns_year=bsns_year)
                count: int = load_dart_financials(datas=financials)
                total_count += count
                print(f"[LOAD] {name}({bsns_year}): {count}개 적재")
            except Exception as e:
                print(f"[ERR] {name}: {type(e).__name__} {e}")
            finally:
                time.sleep(DART_RATE_LIMIT_SLEEP)
        print(f"{name} 총 Load 개수: {total_count}개 적재")

    print("완료")


if __name__ == "__main__":
    try:
        main()
    finally:
        close()
