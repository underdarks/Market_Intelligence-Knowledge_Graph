# build_silver.py (또는 scripts/ 밑에 실행 진입점 하나만)


from market_intelligence_knowledge_graph.config.mongo_db import close, verify
from market_intelligence_knowledge_graph.etl.load.mongo.load_financials import (
    load_financials_from_dart,
    load_financials_from_edgar,
)


# sec edgar + dart raw 데이터를 조회하여 financials 컬렉션(실버 데이터) 적재 파이프라인
def main():
    verify()
    try:
        load_financials_from_edgar()
        load_financials_from_dart()
        print("Financials Silver 적재 완료")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close()
