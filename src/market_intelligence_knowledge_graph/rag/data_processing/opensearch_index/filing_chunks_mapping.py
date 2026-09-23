from market_intelligence_knowledge_graph.config.opensearch_db import get_opensearch

INDEX_NAME = "filing_chunks"

_MAPPING = {
    "settings": {
        "index.knn": True,  # 이 인덱스에서 k-NN(벡터 검색) 쓰겠다고 선언 — 없으면 knn_vector 필드 자체가 안 먹힘
        "number_of_shards": 1,
        "number_of_replicas": 0,  # 로컬 단일 노드라 레플리카 0 (지난번에 합의한 그 이유)
    },
    "mappings": {
        "properties": {
            "entity_id": {"type": "keyword"},  # 예: "cik:0001046179" — 정확 매칭 필터용
            "section_id": {"type": "keyword"},  # 예: "risk_factors"
            "section_title": {"type": "text"},  # 예: "Risk Factors" — 검색 대상 아님, 표시용
            "chunk_text_ko": {
                "type": "text",
                "analyzer": "nori",  # DART(한국어) 청크용
            },
            "chunk_text_en": {
                "type": "text",
                "analyzer": "standard",  # EDGAR(영어) 청크용
            },
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,  # OpenAI text-embedding-3-small 기준
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "faiss",
                },
            },
        }
    },
}


# filing_chunks 인덱스를 위 매핑으로 생성, 이미 존재하면 아무 것도 안 하고 넘어감 (재실행해도 안전하게).
def create_filing_chunks_index() -> None:
    client = get_opensearch()

    if client.indices.exists(index=INDEX_NAME):
        print(f"'{INDEX_NAME}' 인덱스가 이미 존재함, 생성 스킵")
        return

    client.indices.create(index=INDEX_NAME, body=_MAPPING)
    print(f"'{INDEX_NAME}' 인덱스 생성 완료")


if __name__ == "__main__":
    create_filing_chunks_index()
