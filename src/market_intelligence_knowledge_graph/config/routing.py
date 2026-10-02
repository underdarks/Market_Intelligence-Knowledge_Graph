from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class RoutingSettings:
    min_confidence: float  # 분류 신뢰도가 이 값 미만이면 T1(일반 문서)로 간주


@lru_cache
def get_routing_settings() -> RoutingSettings:
    load_dotenv()
    raw = os.getenv("CLASSIFIER_MIN_CONFIDENCE")
    if raw is None:
        raise RuntimeError("환경변수 CLASSIFIER_MIN_CONFIDENCE 가 없습니다")
    return RoutingSettings(min_confidence=float(raw))
