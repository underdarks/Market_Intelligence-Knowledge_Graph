# SEC EDGAR 재무 데이터 원본을 몽고 DB edgar_financials에 적재(메달리온 Bronze)
from typing import Any

from pymongo.results import InsertManyResult

from market_intelligence_knowledge_graph.config.mongo_db import close, get_mongodb, verify
from market_intelligence_knowledge_graph.etl.extraction.common.schemas.schema_financials import (
    DartFinancialBronzeDoc,
    EdgarFinancialBronzeDoc,
)
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_financials import get_edgar_financials


# SEC EDGAR 데이터를 edgar_financials 컬렉션(테이블)에 문서 저장
def load_edgar_financials(datas: list[dict]) -> int:
    if datas is None or not datas:
        return 0

    db = get_mongodb()
    collection = db["edgar_financials"]  # 컬렉션 객체를 얻음. 컬렉션이 없으면 첫 insert때 자동 생성

    # raw dict 하나하나를 DTO로 검증. 필드 누락(이번 fs_div 같은 케이스)이나 타입 오류가 있으면 여기서 바로 에러가 남
    validated: list[EdgarFinancialBronzeDoc] = [EdgarFinancialBronzeDoc(**d) for d in datas]

    # 2. insert 직전에 다시 dict로 변환 (Pydantic 모델 객체는 MongoDB가 못 받음)
    #    exclude={"id"}: id는 아직 None(신규 삽입이니까), MongoDB가 새 _id를 자동 발급하게 둠 (None인 _id를 직접 넣으면 안 됨)
    docs: list[dict[str, Any]] = [v.model_dump(by_alias=True, exclude={"id"}) for v in validated]
    result: InsertManyResult = collection.insert_many(documents=docs)

    return len(result.inserted_ids)  # 저장이 성공된 문서 개수 리턴


# DART 데이터를 edgar_financials 컬렉션(테이블)에 문서 저장
def load_dart_financials(datas: list[dict]) -> int:
    if datas is None or not datas:
        return 0

    db = get_mongodb()
    collection = db["dart_financials"]  # 컬렉션 객체를 얻음. 컬렉션이 없으면 첫 insert때 자동 생성

    validated: list[DartFinancialBronzeDoc] = [DartFinancialBronzeDoc(**d) for d in datas]
    docs: list[dict[str, Any]] = [v.model_dump(by_alias=True, exclude={"id"}) for v in validated]

    result: InsertManyResult = collection.insert_many(docs)

    return len(result.inserted_ids)  # 저장이 성공된 문서 개수 리턴


if __name__ == "__main__":
    verify()
    records = get_edgar_financials("NVDA")
    count = load_dart_financials(records)
    print(f"{count}개 적재됨")

    close()
