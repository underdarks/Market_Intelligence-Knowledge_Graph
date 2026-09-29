# 테스트용 — 질문 하나를 임베딩해서 하이브리드 쿼리 벡터로 사용

from dotenv import load_dotenv

load_dotenv()

from market_intelligence_knowledge_graph.config.opensearch_db import get_opensearch
from market_intelligence_knowledge_graph.rag.data_processing.load.filing_chunk_embedder import embed_texts

# query_text = "삼성전자 반도체 사업의 리스크는 뭐야"
query_text = "what are the main risk factors facing this company"

query_vector = embed_texts([query_text])[0]

client = get_opensearch()

response = client.search(
    index="filing_chunks",
    params={"search_pipeline": "norm-pipeline"},  # ← 파이프라인 적용
    body={
        "size": 5,
        "query": {
            "hybrid": {  # ← bool이 아니라 hybrid
                "queries": [
                    {
                        "bool": {
                            "must": [{"match": {"chunk_text_en": query_text}}],
                            "filter": [{"term": {"entity_id": "cik:0001046179"}}],
                        }
                    },
                    {
                        "knn": {
                            "embedding": {
                                "vector": query_vector,
                                "k": 10,
                                "filter": {"term": {"entity_id": "cik:0001046179"}},
                            }
                        }
                    },
                ]
            }
        },
    },
)
for hit in response["hits"]["hits"][:2]:
    print(hit["_score"], hit["_source"]["section_title"])
    print(hit["_source"]["chunk_text_en"][:300])
    print("---")
