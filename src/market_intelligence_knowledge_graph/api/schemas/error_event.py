from enum import Enum
from typing import Literal

from pydantic import BaseModel


class ErrorCode(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 원인 구분은 로그로. 외부엔 코드만 노출


class ErrorEvent(BaseModel):
    """스트림 도중 실패. done과 함께 종료 신호 역할: 이게 오면 클라이언트는 스트림을 닫는다.
    API 계층 전용: RagService는 예외를 올리고, 이벤트 변환은 여기 책임 (C2 결정)."""

    event: Literal["error"] = "error"
    code: ErrorCode
    message: str  # 사용자용 고정 문구. 예외 메시지(내부 정보)는 절대 넣지 않음
    request_id: str  # 사용자가 문의할 때 로그를 찾는 키
