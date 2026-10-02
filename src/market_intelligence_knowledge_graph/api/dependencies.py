from fastapi import Request

from market_intelligence_knowledge_graph.rag.orchestration.rag_service import RagService


def get_rag_service(request: Request) -> RagService:
    # lifespan에서 만든 싱글톤을 꺼내기만 함. 생성 책임은 lifespan 한 곳
    # 핸들러: service: RagService = Depends(get_rag_service)
    return request.app.state.rag_service
