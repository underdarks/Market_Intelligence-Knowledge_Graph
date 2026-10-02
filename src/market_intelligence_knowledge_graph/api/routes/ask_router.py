from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from market_intelligence_knowledge_graph.api.dependencies import get_rag_service
from market_intelligence_knowledge_graph.api.schemas.ask_request import AskRequest
from market_intelligence_knowledge_graph.api.streaming import stream_sse
from market_intelligence_knowledge_graph.rag.orchestration.rag_service import RagService

ask_router = APIRouter()


@ask_router.post("/ask")
async def ask(body: AskRequest, request: Request, service: RagService = Depends(get_rag_service)) -> StreamingResponse:
    # body 검증 실패(빈 질문, 길이 초과, 모르는 필드)는 여기 오기 전에 FastAPI가 422로 응답
    events = service.response_answer_stream(body.to_answer_request())  # 제너레이터 생성만 (아직 실행 안 됨)
    return StreamingResponse(
        stream_sse(events=events, req_id=request.state.request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",  # 중간 캐시가 스트림을 저장하지 않게
            "X-Accel-Buffering": "no",  # nginx 프록시가 버퍼링하면 토큰이 한 번에 몰려 나옴: 끔
        },
    )
