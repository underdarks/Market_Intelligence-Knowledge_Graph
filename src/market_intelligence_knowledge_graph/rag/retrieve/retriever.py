from typing import Protocol

from market_intelligence_knowledge_graph.rag.retrieve.schema.schema import RetrievedItem, RetrievalQuery


class Retriever(Protocol):
    """검색기 공통 인터페이스 (Java의 interface와 같은 역할, 단 상속 없이 모양만 맞으면 인정).

    async로 통일: 동기 라이브러리를 쓰는 검색기는 내부에서 to_thread로 감싼다.
    그래야 RagService가 검색기마다 동기/비동기를 구분하지 않고 gather로 병렬 실행할 수 있다.
    """

    name: str  # plan_route가 고르는 키. 로그에도 이 이름으로 찍힘

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievedItem]: ...
