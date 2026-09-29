from openai import AsyncOpenAI, AsyncStream
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from market_intelligence_knowledge_graph.config.config import LLM_GATEWAY_API_KEY, LLM_GATEWAY_BASE_URL
from market_intelligence_knowledge_graph.config.llm_gateway import get_llm_answer_model, get_llm_gateway_client

_client = AsyncOpenAI(base_url=LLM_GATEWAY_BASE_URL, api_key=LLM_GATEWAY_API_KEY)


async def stream_answer(
    system_prompt: str, user_prompt: str, model: str | None = None
) -> AsyncStream[ChatCompletionChunk]:
    """
    LLM 게이트웨이(LiteLLM Proxy)를 통해 LLM 스트리밍 호출. 토큰을 하나씩 yield.
    이 함수는 async generator다. yield를 쓴다는 것은 "함수가 끝나야 값을 반환"하는 게 아니라, "값이 생길 때마다 그 자리에서 잠깐 멈추고, 호출한 쪽에 제어권과 값을 함께 넘긴다"는 뜻이다.

    호출하는 쪽에서 async for로 이 함수를 순회하면:
      1) 다음 값을 요청 → 함수가 멈췄던 지점(또는 처음)부터 실행 재개
      2) yield에 도달 → 값을 건네주고 함수 실행을 그 자리에서 일시정지
      3) 호출한 쪽이 그 값으로 뭔가 처리 (예: SSE로 즉시 전송)
      4) 다시 다음 값을 요청하면 1)로 돌아가 반복

    이 방식 덕분에 OpenAI 응답 전체가 끝날 때까지 기다리지 않고, 토큰이 생성되는 즉시 하나씩 호출한 쪽(나중에 C3의 SSE 응답)으로 전달할 수 있다
    — ChatGPT 화면에 글자가 타이핑되듯 나오는 것과 같은 원리. 만약 return으로 리스트를 통째로 반환했다면, 사용자는 전체 답변이 완성될 때까지 수 초간 아무것도 못 보고 기다려야 했을 것이다.
    """

    stream: AsyncStream[ChatCompletionChunk] = await get_llm_gateway_client().chat.completions.create(
        model=model or get_llm_answer_model(),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        stream=True,
    )

    try:
        async for chunk in stream:
            # usage 전용 청크처럼 choices가 빈 청크가 올 수 있어서 건너뜀
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content
    finally:
        # 정상 종료, 예외, 소비자가 중간에 끊는 경우 모두 여기를 지난다. stream.close()는 밑에 깔린 HTTP 응답을 닫는다.
        # 안 닫으면 연결이 열린 채 남고, 종료 시점에 asyncio가 강제로 닫다가 에러를 낼 수 있다.
        await stream.close()
