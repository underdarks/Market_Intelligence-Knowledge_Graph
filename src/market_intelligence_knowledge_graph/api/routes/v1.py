from fastapi import APIRouter
from market_intelligence_knowledge_graph.api.routes.ask_router import ask_router

# 버전 묶음 라우터: 공통 prefix를 여기서만 선언
# v2가 생기면 v2.py를 만들고, 바뀐 도메인 라우터만 교체해서 include
api_v1_router = APIRouter(prefix="/api/v1")  # v1 API 라우터 생성
api_v1_router.include_router(ask_router)
# 도메인이 늘면 여기에 한 줄씩: api_v1_router.include_router(chats_router)
