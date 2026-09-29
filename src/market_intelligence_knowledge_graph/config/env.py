import os
from dotenv import load_dotenv

"""config/env.py
필수 환경변수 읽기 공용 헬퍼. 값이 없으면 기본값으로 얼버무리지 않고 즉시 실패시킨다 (fail-fast).
이 모듈이 import되는 시점에 .env를 로드하므로, 이 헬퍼를 거치는 설정은 import 순서 문제가 없다.
"""

load_dotenv()


def require_str(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 {name}가 설정되지 않았습니다 (.env 확인)")
    return value


def require_int(name: str) -> int:
    value = require_str(name)
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"환경변수 {name}는 정수여야 합니다: {value!r}") from None
