import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from market_intelligence_knowledge_graph.api.schemas.error_event import ErrorCode, ErrorEvent
from market_intelligence_knowledge_graph.api.sse import to_sse

log = logging.getLogger(__name__)

_ERROR_MESSAGE = "답변을 만드는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요."


async def stream_sse(events: AsyncGenerator, req_id: str) -> AsyncGenerator[str, None]:
    """서비스 이벤트 스트림 -> SSE 문자열 스트림. 예외·연결 끊김·로그를 여기서 처리."""
    started = time.perf_counter()  # 경과 시간 측정용 고해상도 시계 (시스템 시각 변경에 영향 없음)
    sent = 0  # 보낸 이벤트 수: 끊김·에러가 몇 번째에서 났는지 추적
    last_event: str | None = None  # 마지막 상태: done / error / disconnected 등

    try:
        async for event in events:
            yield to_sse(event)
            sent += 1
            last = event.event

    # 연결 끊김은 두 경로로 옴:
    #  - CancelledError: 안쪽(LLM 스트림 대기 중)에서 태스크가 취소될 때
    #  - GeneratorExit: 이 함수가 yield에서 멈춘 상태로 닫힐 때
    # 둘 다 BaseException 계열이라 아래 except Exception에는 안 잡힘 (의도된 분리)
    except (asyncio.CancelledError, GeneratorExit):
        last_event = "disconnected"
        log.info("client disconnected request_id=%s sent=%d", req_id, sent)
        raise  # 반드시 다시 올림. 삼키면 취소가 무시돼 LLM 호출이 계속 돎. 여기서 yield도 금지

    except Exception:
        # logger.exception: error 레벨 + 스택 트레이스 자동 포함
        log.exception("stream failed request_id=%s sent=%d", req_id, sent)
        yield to_sse(ErrorEvent(code=ErrorCode.INTERNAL_ERROR, message=_ERROR_MESSAGE, request_id=req_id))
        last_event = "error"

    finally:
        # 안쪽 제너레이터(RagService -> generate_answer -> LLM 스트림)를 즉시 닫음
        # 이미 끝났으면 아무 일도 안 함 (여러 번 호출해도 안전)
        await events.aclose()
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info(
            "stream end request_id=%s last=%s sent=%d elapsed_ms=%.0f",
            req_id,
            last_event,
            sent,
            elapsed_ms,
        )
