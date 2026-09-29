from market_intelligence_knowledge_graph.config.mongo_db import get_mongodb
from market_intelligence_knowledge_graph.etl.extraction.common.schemas.schema_filling_text import FilingTextBronzeDoc


# FilingTextBronzeDoc 리스트를 filing_text 컬렉션에 적재.
def load_filing_text_documents(docs: list[FilingTextBronzeDoc]) -> int:
    if not docs:
        return 0

    db = get_mongodb()
    collection = db["filing_text"]

    # insert 직전에 다시 dict로 변환 (Pydantic 모델 객체는 MongoDB가 못 받음)
    # exclude={"id"}: id는 아직 None(신규 삽입이니까), MongoDB가 새 _id를 자동 발급하게 둠 (None인 _id를 직접 넣으면 안 됨)
    payload = [d.model_dump(exclude={"id"}) for d in docs]
    result = collection.insert_many(payload)

    return len(result.inserted_ids)

