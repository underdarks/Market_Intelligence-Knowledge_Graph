# 잠정: C1(Entity Linking) 구현 시 회사 메타데이터 기반으로 교체하고 이 매핑은 삭제한다.
# 인덱싱 쪽 언어 판별 규칙과 지금은 이중으로 존재하는 상태라서 C1에서 한 곳으로 합쳐야 한다.
import asyncio
from collections.abc import AsyncGenerator, Callable

from market_intelligence_knowledge_graph.config.rag_api import get_search_top_k
from market_intelligence_knowledge_graph.rag.generation.answer_generator import generate_answer
from market_intelligence_knowledge_graph.rag.search.schema.retrieved_item import RetrievedItem
from market_intelligence_knowledge_graph.rag.search.search_filing import search_filing_chunks

_LANG_FIELD_BY_PREFIX = {"dart": "chunk_text_ko", "cik": "chunk_text_en"}


class RagService:
    def __init__(self) -> None:
        

    # entity_id 접두사로 검색 필드를 결정. 모르는 접두사는 ValueError
    def resolve_lang_field(entity_id: str) -> str:
        prefix = entity_id.split(":", 1)[0]
        try:
            return _LANG_FIELD_BY_PREFIX[prefix]

        except KeyError:
            raise ValueError(f"지원하지 않는 entity_id : {entity_id!r}") from None

    async def answer_question(question: str, entity_id: str, lang_field: str) -> AsyncGenerator[AnswerEvent, None]:
        """
        질문 하나를 받아 AnswerEvent 스트림을 내보내는 오케스트레이션 진입점.

        역할: 단계의 "순서"를 정한다. 실제 일은 각 계층이 한다.
        1. 검색 (search_filing_chunks)
        2. 생성 위임 (generate_answer)
        """

        # asyncio.to_thread는 동기(blocking) 함수를 별도의 스레드에서 실행하여 이벤트 루프가 멈추지 않도록 도와주는 함수입니다.(uvicorn이 싱글 이벤트 루프 기반이므로)
        retrieved_items: list[RetrievedItem] = await asyncio.to_thread(
            search_filing_chunks, question, entity_id, lang_field, get_search_top_k()
        )

        async for event in generate_answer(question, items=retrieved_items):
            yield event
