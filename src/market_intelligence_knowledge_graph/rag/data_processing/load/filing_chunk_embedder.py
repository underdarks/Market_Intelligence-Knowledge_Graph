from openai import OpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse

from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_section import FilingSection

_client = OpenAI()  # OpenAI() 객체는 생성될 때 내부적으로 Python의 os.environ.get("OPENAI_API_KEY")를 조회합니다.


# source 기준  이 청크가 들어갈 필드명을 반환. 매핑에서 정한 chunk_text_ko/en과 짝맞춤
def get_language_field(section: FilingSection) -> str:
    return "chunk_text_ko" if section.source == "dart" else "chunk_text_en"


# 청크 텍스트를 OpenAI 임베딩으로 변환. 1536차원 벡터 반환
def embed_texts(texts: list[str]) -> list[list[float]]:
    res: CreateEmbeddingResponse = _client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in res.data]
