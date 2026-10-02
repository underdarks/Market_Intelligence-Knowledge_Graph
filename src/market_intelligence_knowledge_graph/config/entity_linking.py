from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


# 엔티티 리킹 설정값
@dataclass(frozen=True)
class EntityLinkingSettings:
    min_alphanum_len: int  # 영문·숫자 별칭 최소 길이. 미만이면 인덱스 제외 ("MU" 오탐 방지)


@lru_cache
def get_entity_linking_settings() -> EntityLinkingSettings:
    load_dotenv()
    raw = os.getenv("ALIAS_MIN_ALPHANUM_LEN")
    if raw is None:
        raise RuntimeError("환경변수 ALIAS_MIN_ALPHANUM_LEN 이 없습니다")
    return EntityLinkingSettings(min_alphanum_len=int(raw))
