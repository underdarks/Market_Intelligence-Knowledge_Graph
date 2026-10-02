from typing import Protocol


class _SseEvent(Protocol):
    """event 필드를 가진 Pydantic 모델이면 무엇이든 (AnswerEvent, ErrorEvent)."""

    event: str

    def model_dump_json(self, *, exclude: set[str]) -> str: ...


def to_sse(event: _SseEvent) -> str:
    """이벤트 1개 -> SSE 텍스트 프레임.

    형식: event: <종류>\\ndata: <JSON>\\n\\n  (빈 줄이 프레임 구분자)
    """
    # event 필드는 "event:" 줄에 이미 쓰므로 data에서 제외
    # model_dump_json은 한글을 이스케이프하지 않고, 문자열 속 줄바꿈은 \n으로 이스케이프함
    # -> data 줄이 한 줄로 유지돼서 SSE 형식이 안 깨짐
    data = event.model_dump_json(exclude={"event"})
    return f"event: {event.event}\ndata: {data}\n\n"
