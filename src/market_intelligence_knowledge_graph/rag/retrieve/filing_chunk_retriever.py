# entity_id 접두사 -> OpenSearch 검색 필드
# DART 회사는 한글 본문, EDGAR(cik) 회사는 영문 본문 필드를 검색한다
# 이 매핑은 OpenSearch 인덱스 구조 지식이라 이 검색기 안에만 둔다 (RagService·API는 모름)
import asyncio

from market_intelligence_knowledge_graph.rag.retrieve.schema.schema import RetrievalQuery, RetrievedItem
from market_intelligence_knowledge_graph.rag.retrieve.search_filing import search_filing_chunks

_LANG_FIELD_BY_PREFIX: dict[str, str] = {
    "dart": "chunk_text_ko",
    "cik": "chunk_text_en",
}


class FilingChunkRetriever:
    """공시 본문 청크 검색기 (OpenSearch 하이브리드 검색). Retriever 프로토콜 구현체."""

    # 클래스 속성: 인스턴스 없이 FilingChunkRetriever.name 으로 참조 가능
    # plan_route가 문자열 대신 이 속성을 참조해서, 이름이 바뀌어도 한 곳만 고치면 됨
    name = "filing_chunks"

    def __init__(self, top_k: int) -> None:
        self._top_k = top_k

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedItem]:
        lang_field = self._resolve_lang_field(query.entity_id)

        return await asyncio.to_thread(
            search_filing_chunks, query=query.question, lang_field=lang_field, entity_id=query.entity_id, k=self._top_k
        )

    @staticmethod  # self가 필요 없는 메서드 (Java의 static 메서드)
    def _resolve_lang_field(entity_id: str) -> str:
        prefix = entity_id.split(":", 1)[0]  # "dart:00126380" -> "dart"
        try:
            return _LANG_FIELD_BY_PREFIX[prefix]
        except KeyError:
            # 링커가 Neo4j의 ID를 주므로 여기 오면 데이터 버그. 조용히 넘기지 않음
            # from None: KeyError 트레이스백을 숨기고 ValueError만 보여줌
            raise ValueError(f"지원하지 않는 entity_id 접두사: {entity_id!r}") from None
