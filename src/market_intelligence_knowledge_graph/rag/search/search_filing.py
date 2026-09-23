from opensearchpy import OpenSearch

from market_intelligence_knowledge_graph.config.opensearch_db import get_opensearch
from market_intelligence_knowledge_graph.rag.data_processing.load.filing_chunk_embedder import embed_texts
from market_intelligence_knowledge_graph.rag.data_processing.schema.indexs import FILING_CHUNKS
from market_intelligence_knowledge_graph.rag.search.schema.retrieved_item import RetrievedItem


def search_filing_chunks(query: str, entity_id: str, lang_field: str, k: int = 5):
    """
     opensearch filing_chunks 인덱스 하이브리드 검색(bm25+knn)

    Args:
        query_text: 사용자 질문 원문
        entity_id: Entity Linking으로 얻은 회사 식별자 (지금은 하드코딩)
        lang_field: "chunk_text_ko" | "chunk_text_en"
        k: 반환할 최대 결과 수
    """

    # 1. 임베딩 변환
    query_vector: list[float] = embed_texts(texts=list(query))[0]

    # 2. opensearch 커넥션
    client: OpenSearch = get_opensearch()

    # 3.hybrid 쿼리
    body = (
        {
            "size": 5,
            "query": {
                "hybrid": {
                    "queries": [
                        {
                            "bool": {
                                "must": [{"match": {"chunk_text_en": query}}],
                                "filter": [{"term": {"entity_id": entity_id}}],
                            }
                        },
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_vector,
                                    "k": k,
                                    "filter": {"term": {"entity_id": entity_id}},
                                }
                            }
                        },
                    ]
                }
            },
        },
    )

    res = client.search(
        index=FILING_CHUNKS,
        params={
            "search_pipeline": "norm-pipeline",
        },
        body=body,
    )

    retrieved_items: list[RetrievedItem] = []
    for hit in res["hits"]["hits"]:
        src = hit["_source"]
        content = src.get("chunk_text_en") or src.get("chunk_text_ko") or ""
        ret = RetrievedItem(
            source_type="hybrid_search",
            doc_id=hit["_id"],
            entity_id=src["entity_id"],
            section_title=src["section_title"],
            content=content,
            score=hit["_score"],
        )
        retrieved_items.append(ret)
