import time

from market_intelligence_knowledge_graph.config.config import SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.config.mongo_db import close, verify
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_financials import get_edgar_financials
from market_intelligence_knowledge_graph.etl.load.mongo.load_financials_raw import load_edgar_financials
from market_intelligence_knowledge_graph.sample.targets import TARGET_US_COMPANYS


# SEC EDGAR 기업 재무재표 적재 파이프라인
def main():
    verify()

    for ticker in TARGET_US_COMPANYS:
        try:
            financials = get_edgar_financials(ticker=ticker)
            count = load_edgar_financials(datas=financials)
            print(f"[LOAD] {ticker}: {count}개 적재")

        except Exception as e:
            print(f"[ERR] {ticker}: {type(e).__name__} {e}")
        finally:
            time.sleep(SEC_RATE_LIMIT_SLEEP)

    print("완료")


if __name__ == "__main__":
    try:
        main()
    finally:
        close()
