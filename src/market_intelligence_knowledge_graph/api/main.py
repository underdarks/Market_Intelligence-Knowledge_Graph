from contextlib import asynccontextmanager
import logging
from edgar import settings
from fastapi import FastAPI
from market_intelligence_knowledge_graph.api.middleware import RequestIdMiddleware
from market_intelligence_knowledge_graph.config.entity_linking import get_entity_linking_settings
from market_intelligence_knowledge_graph.config.llm_gateway import close_llm_gateway_client
from market_intelligence_knowledge_graph.config.logging import setup_logging
from market_intelligence_knowledge_graph.config.rag_api import get_search_top_k
from market_intelligence_knowledge_graph.config.routing import get_routing_settings
from market_intelligence_knowledge_graph.rag.classification.classfier import StubQuestionClassifier
from market_intelligence_knowledge_graph.rag.classification.planner import RoutePlanner
from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import (
    AliasIndex,
    CompanyRecord,
    build_alias_index,
)
from market_intelligence_knowledge_graph.rag.entity_linking.company_index_loader import load_company_records
from market_intelligence_knowledge_graph.rag.entity_linking.linker import DictionaryEntityLinker
from market_intelligence_knowledge_graph.rag.orchestration.rag_service import RagService
from market_intelligence_knowledge_graph.rag.retrieve.filing_chunk_retriever import FilingChunkRetriever
from market_intelligence_knowledge_graph.api.routes.v1 import api_v1_router

log = logging.getLogger(__name__)
setup_logging()


# FastAPI 애플리케이션의 시작(Startup)과 종료(Shutdown) 시점에 실행할 코드를 한곳에서 관리하는 비동기 이벤트 핸들(DB 커넥션 풀, 외부 API 호출 등)
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("서버 시작: 초기화 진행")

    # 엔티티 리킹 설정
    settings = get_entity_linking_settings()
    company_records = load_company_records()
    index: AliasIndex = build_alias_index(company_records, min_alphanum_len=settings.min_alphanum_len)
    app.state.entity_linker = DictionaryEntityLinker(index=index)
    log.info("별칭 인덱스 준비 완료: %d개 항목", len(index.entries))

    # 라우팅 설정
    routing = get_routing_settings()
    app.state.rag_service = RagService(
        classifier=StubQuestionClassifier(),
        linker=DictionaryEntityLinker(index=index),
        route_planner=RoutePlanner(min_confidence=routing.min_confidence),
        retrievers=[FilingChunkRetriever(top_k=get_search_top_k())],
    )

    try:
        yield  # 여기서 멈춘 채로 서버가 요청을 처리
    finally:
        # ---- 종료 (yield 후) ----
        await close_llm_gateway_client()
        log.info("서버 종료: 리소스 정리 완료")


app = FastAPI(title="MIKG RAG API", version="0.0.1", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)  # 요청별 고유 ID 부여
app.include_router(api_v1_router)  # v1 API 라우터 포함


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
