# api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from market_intelligence_knowledge_graph.config.llm_gateway import close_llm_gateway_client


# FastAPI 애플리케이션의 시작(Startup)과 종료(Shutdown) 시점에 실행할 코드를 한곳에서 관리하는 비동기 이벤트 핸들(DB 커넥션 풀, 외부 API 호출 등)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("▶ 서버 시작 — DB 커넥션 풀 초기화 등 여기서")
    yield
    await close_llm_gateway_client()
    print("■ 서버 종료 — 리소스 정리 여기서")


app = FastAPI(title="MIKG RAG API",version="0.0.1" lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
