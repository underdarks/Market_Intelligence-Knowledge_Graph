from dataclasses import dataclass
from functools import lru_cache
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class ApiSettings:
    question_max_length: int  # 질문 최대 글자 수. 비용 폭주·프롬프트 주입 완화용 상한


@lru_cache
def get_api_settings() -> ApiSettings:
    load_dotenv()
    raw = os.getenv("ASK_QUESTION_MAX_LENGTH")
    if raw is None:
        raise RuntimeError("환경변수 ASK_QUESTION_MAX_LENGTH 가 없습니다")
    return ApiSettings(question_max_length=int(raw))
