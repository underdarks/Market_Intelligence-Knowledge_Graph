from functools import lru_cache
from openai import AsyncOpenAI
from market_intelligence_knowledge_graph.config.env import require_str


def get_llm_answer_model() -> str:
    return require_str("LLM_ANSWER_MODEL")


# lru_cache:  함수 결과를 메모리에 캐싱하는 데코레이터. 같은 인자로 다시 호출하면 함수를 실행하지 않고 저장된 결과를 즉시 반환합니다.
@lru_cache(maxsize=1)
def get_llm_gateway_client() -> AsyncOpenAI:
    """
    LRU: Least Recently Used. 캐시가 꽉 차면 가장 오래 안 쓴 항목부터 버림
    maxsize=1: 최근 1개 결과만 저장
    인자 없는 함수 + maxsize=1: 사실상 싱글톤 패턴 (최초 1회 실행 후 계속 재사용)
    """
    return AsyncOpenAI(
        base_url=require_str("LLM_GATEWAY_BASE_URL"),
        api_key=require_str("LLM_GATEWAY_API_KEY"),
        timeout=float(require_str("LLM_GATEWAY_TIMEOUT_SECONDS")),
        max_retries=0,  # 재시도는 게이트웨이(LiteLLM) 책임. 여기서도 하면 재시도가 곱해진다
    )


# 앱 종료 시 호출
async def close_llm_gateway_client() -> None:
    if get_llm_gateway_client.cache_info().currsize:  # 캐시에 저장된 항목 수
        await get_llm_gateway_client().close()  # 캐시된 싱글톤 인스턴스를 꺼내서 비동기 close(커넥션 풀, keep-alive 소켓 등 리소스 반환)
        get_llm_gateway_client.cache_clear()
