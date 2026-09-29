from collections.abc import AsyncGenerator

from market_intelligence_knowledge_graph.rag.generation.context_builder import build_context
from market_intelligence_knowledge_graph.rag.generation.llm_gateway_client import stream_answer
from market_intelligence_knowledge_graph.rag.generation.prompt import (
    NO_EVIDENCE_MESSAGE,
    SYSTEM_PROMPT,
    build_user_message,
)
from market_intelligence_knowledge_graph.rag.schema.answer_event import (
    AnswerEvent,
    DoneEvent,
    SourceItem,
    SourcesEvent,
    TokenEvent,
)
from market_intelligence_knowledge_graph.rag.search.schema.retrieved_item import RetrievedItem


async def generate_answer(question: str, items: list[RetrievedItem]) -> AsyncGenerator[AnswerEvent, None]:
    """
    LLM 게이트웨이 호출과 이벤트 스트리밍을 담당한다.(items: 검색 결과)
    이벤트 순서 (이 규칙을 이 함수가 보장한다)
      정상:      SourcesEvent -> TokenEvent x N -> DoneEvent
      근거 없음: SourcesEvent(빈 리스트) -> TokenEvent(안내 문구) -> DoneEvent
    예외는 삼키지 않고 그대로 올린다. 에러를 이벤트로 바꾸는 건 API 계층(C3) 책임.
    """

    # 1. 근거 목록 생성.
    #    build_context()가 프롬프트에 붙이는 [출처 n]과 이 index는 같은 items를
    #    같은 순서로 enumerate해서 나온 번호다. 이 사이에 정렬/필터를 끼우면
    #    LLM이 인용한 [2]와 화면의 [2]가 서로 다른 청크를 가리키게 된다.
    source_items: list[SourceItem] = [
        SourceItem(
            index=idx,
            doc_id=item.doc_id,
            entity_id=item.entity_id,
            section_title=item.section_title,
            content=item.content,
            score=item.score,
        )
        for idx, item in enumerate(items, start=1)
    ]

    # 2. 근거를 토큰보다 먼저 내보낸다.
    #    프론트가 출처 카드를 먼저 그려두면, 뒤이어 스트리밍되는 [1] 마커를
    #    바로 카드와 연결할 수 있다. 근거가 0건이어도 빈 리스트로 이 이벤트는 보낸다
    #    (프론트가 "근거 없음"과 "아직 안 옴"을 구분할 수 있게).
    yield SourcesEvent(sources=source_items)

    # 3. 근거 없으면 LLM을 호출하지 않는다.(###TODO: 추후 수정 필요)
    #    컨텍스트가 비면 모델이 일반 지식으로 채우려는 경향이 강해서
    #    시스템 프롬프트 규칙 5번만으로는 환각을 완전히 못 막는다.
    #    호출 자체를 스킵하면 비용도 안 든다.
    #    async generator에서는 값 없는 bare return만 허용된다 (return 값 불가).
    if not items:
        yield TokenEvent(text=NO_EVIDENCE_MESSAGE)
        yield DoneEvent()
        return

    # 4. 프롬프트 조립
    context = build_context(items=items)
    user_prompt = build_user_message(context=context, question=question)

    # 5. LLM 게이트웨이 호출. 토큰을 하나씩 yield.
    # async for는 비동기 이터레이터를 반복할떄 사용(반복을 통해 다음값을 await을 알아서해줌)
    # yield는 값을 반환하고 함수 실행을 일시정지. 호출한 쪽에서 다시 next()를 호출하면 함수가 멈췄던 지점부터 실행 재개
    # async generator는 yield를 쓴다는 것은 "함수가 끝나야 값을 반환"하는 게 아니라, "값이 생길 때마다 그 자리에서 잠깐 멈추고, 호출한 쪽에 제어권과 값을 함께 넘긴다"
    async for token in stream_answer(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt):
        yield TokenEvent(text=token)

    # 6. 정상 종료 신호. 이 이벤트가 있어야 프론트가 정상 종료와 연결 끊김을 구분한다.
    #    5번 도중 예외가 나면 여기까지 오지 않으므로, DoneEvent가 없다는 것 자체가 실패 신호가 된다.
    yield DoneEvent()
