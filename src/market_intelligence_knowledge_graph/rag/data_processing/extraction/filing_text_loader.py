from market_intelligence_knowledge_graph.config.mongo_db import get_mongodb
from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_section import FilingSection


# mongo db에서 filing_text 컬렉션에서 청킹 대상이 될 섹션들을 조회, 청킹 함수에 그대로 넘길 수 있는 형태로 반환.
def get_filing_sections() -> list[FilingSection]:

    db = get_mongodb()
    collection = db["filing_text"]

    # 청킹에 필요 없는 필드(적재 메타데이터 등)는 애초에 안 가져오도록 projection 지정
    # _id는 기본적으로 항상 딸려오니 명시적으로 0 처리해서 제외
    cursor = collection.find(
        {},
        {
            "_id": 0,
            "entity_id": 1,
            "source": 1,
            "section_id": 1,
            "section_title": 1,
            "text": 1,
        },
    )
    # 타입 검증, 필드가 하나라도 없거나 타입이 안 맞으면 여기서 즉시 에러로 잡힘 (나중에 청킹 단계에서 죽는 게 아니라)
    sections: list[FilingSection] = [FilingSection(**doc) for doc in cursor]
    return sections
