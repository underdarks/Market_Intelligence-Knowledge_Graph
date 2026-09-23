from market_intelligence_knowledge_graph.config.opensearch_db import get_opensearch
from market_intelligence_knowledge_graph.rag.data_processing.load.filing_chunk_embedder import embed_texts
from market_intelligence_knowledge_graph.rag.data_processing.schema.indexs import FILING_CHUNKS


# golden set 정답 라벨링
def inspect_golden_set(query: str, lang_field: str = "chunk_text_en", entity_id: str | None = None, size: int = 10):
    query_vector = embed_texts(texts=[query])[0]
    client = get_opensearch()

    bool_query: dict = {"must": [{"match": {lang_field: query}}]}
    knn_query: dict = {"embedding": {"vector": query_vector, "k": size}}
    if entity_id:  # 회사 지정 시에만 필터 적용, 양쪽 서브쿼리 모두에 걸어야 함
        bool_query["filter"] = [{"term": {"entity_id": entity_id}}]
        knn_query["embedding"]["filter"] = {"term": {"entity_id": entity_id}}

    res = client.search(
        index=FILING_CHUNKS,
        params={
            "search_pipeline": "norm-pipeline",
        },
        body={
            "size": size,
            "query": {"hybrid": {"queries": [{"bool": bool_query}, {"knn": knn_query}]}},
        },
    )

    for rank, hit in enumerate(res["hits"]["hits"], start=1):
        src = hit["_source"]
        text = src.get("chunk_text_en") or src.get("chunk_text_ko") or ""
        print(
            f"rank: {rank} | score: {hit['_score']:.4f} | doc_id: {hit['_id']} | entity_id: {src['entity_id']} | section: {src['section_title']}"
        )
        print(f"text: {text[:200].strip()}...")
        print()


if __name__ == "__main__":
    inspect_golden_set("Micron revenue and gross margin change", "chunk_text_en", "cik:0000723125")
