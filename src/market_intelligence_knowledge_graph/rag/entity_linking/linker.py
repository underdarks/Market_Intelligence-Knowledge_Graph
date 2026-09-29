from typing import Protocol

from market_intelligence_knowledge_graph.rag.entity_linking.schema.link_result import LinkResult


# Protocol은 덕타이핑으로, java의 interface와 동일하지만 구현체는 implements를 안 적어고 메서드 구현하면됨
# 자바 컴파일러 같은 타입 검사기(mypy)는 알아서 인터페이스를 구현했다고 인정해 주는 스마트한 타입
class EntityLinker(Protocol):
    """
    질문에서 회사를 찾는 공통 인터페이스. RagService는 이것만 안다.
    지금 구현은 메모리 조회라 async가 필요 없지만, LLM 폴백이 붙어도 호출부가 안 바뀌게 처음부터 async로 맞춘다.
    """

    async def link(self, question: str) -> LinkResult: ...
