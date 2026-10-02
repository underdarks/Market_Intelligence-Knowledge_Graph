from collections import defaultdict
import logging
import re
from dataclasses import dataclass

from market_intelligence_knowledge_graph.rag.entity_linking.normalizer import normalize, squash

logger = logging.getLogger(__name__)

# 영문·숫자로만 된 별칭이 이 길이 미만이면 인덱스에서 뺀다.
# Micron 티커 "MU"가 "community" 같은 단어 안에서 걸리는 오탐을 막기 위한 값이다.
# 한글 별칭에는 적용하지 않는다 ("삼전"은 2자여도 유지).
MIN_ALPHANUM_ALIAS_LENGTH = 3

_HANGUL = re.compile(r"[가-힣]")


class AliasConflictError(RuntimeError):
    """
    정규화한 별칭이 서로 다른 회사에 걸려 있을 때 던진다.
    요청 중에 조용히 한쪽 회사로 확정되는 게 가장 위험해서, 기동 시점에 서버를 못 뜨게 막는다.
    """


# dataclass(frozen=True)는 한 번 생성되면 내부 값을 변경할 수 없는 불변(Immutable) 객체로 만든다
@dataclass(frozen=True)
class CompanyRecord:
    """
    인덱스 구성에 필요한 Company 값만 옮겨 담은 그릇 (입력).
    리스트가 아니라 tuple인 이유: frozen이라 만든 뒤 바뀌지 않게 하려는 것.
    Neo4j에서 값이 None으로 올 수 있어서 로더(C1-7)가 빈 tuple로 바꿔서 넘긴다.
    """

    entity_id: str
    name: str  # 정식명 (예: "삼성전자(주)")
    aliases: tuple[str, ...]  # 승인된 별칭 (DART 영문명 + 우리가 넣은 것)
    tickers: tuple[str, ...]  # 티커/종목코드 (예: "NVDA", "005930")
    former_names: tuple[str, ...]  # 옛 이름 (예: "Broadcom Ltd")


@dataclass(frozen=True)
class AliasEntry:
    """인덱스의 항목 1개. 별칭 하나가 어느 회사의 것인지와 매칭 방식을 담는다 (내부용)."""

    entity_id: str
    name: str  # 화면에 보여줄 회사명 (LinkedEntity.name으로 그대로 나감)
    alias: str  # 원문 그대로 (LinkedEntity.matched_alias로 나감)
    key: str  # 매칭에 쓰는 정규화 키
    is_hangul: bool  # 매칭 방식을 가른다 (아래 설명)
    # is_hangul=True : key는 squash 결과(공백 없음). 질문도 squash해서 "부분 문자열"로 찾는다.("SK 하이닉스"와 "SK하이닉스"를 같게 보려고)
    # is_hangul=False: key는 normalize 결과(공백 유지). 질문에서 "앞뒤가 영숫자가 아닐 때만" 찾는다.(단어 경계 매칭. "nvda"가 다른 단어 안에서 걸리지 않게)


@dataclass(frozen=True)
class AliasIndex:
    """매칭 대상 전체 (출력). 항목 수가 수십~수백 개 수준이라 지금은 선형 스캔으로 충분하다."""

    entries: tuple[AliasEntry, ...]


def build_alias_index(company_records: list[CompanyRecord], min_alphanum_len: int) -> AliasIndex:
    """
    회사 목록으로 별칭 인덱스(메모리 캐싱)를 만든다.

    Args:
        min_alphanum_len: 영문·숫자 별칭 최소 길이. 미만이면 제외 (config에서 주입, 하드코딩 금지)

    충돌 정책:
        서로 다른 회사가 같은 key를 가지면 그 key는 "모든 회사에서" 제외하고 경고 로그를 남긴다.
        먼저 들어온 회사에 주는 방식은 Neo4j 반환 순서에 따라 결과가 바뀌고,
        조용히 한쪽 회사로 확정되는 가장 위험한 상황을 만든다. 제외하면 not_found로 떨어져 되묻기로 간다.

    Raises:
        ValueError: 정규화하면 빈 문자열이 되는 값이 있을 때 (예: 별칭이 "(주)")
    """

    # defaultdict(set): 없는 key에 접근하면 빈 set을 자동 생성하는 dict
    # (if key not in d: d[key] = set() 를 매번 안 써도 됨)
    owners_by_key: dict[str, set[str]] = defaultdict(set)  # key -> 이 key를 가진 entity_id 집합
    candidates: list[AliasEntry] = []  # 회사 내부 중복만 거른 후보 (충돌 검사 전)

    # ---- 1패스: 후보 수집 ----
    for company in company_records:
        seen_keys: set[str] = set()  # 이 회사 안에서 이미 나온 key (회사 내부 중복 제거용)

        # name을 맨 앞에 둔다: 회사 내부 중복 시 먼저 나온 원문이 남는데,
        # 그 원문이 되묻기 화면의 matched_alias로 나가므로 정식명이 남게 하려는 것
        values = (company.name, *company.aliases, *company.tickers, *company.former_names)

        for value in values:
            is_hangul = bool(_HANGUL.search(value))
            # 한글은 공백 없는 키(부분 문자열 매칭용), 영문·숫자는 공백 유지 키(단어 경계 매칭용)
            key = squash(value) if is_hangul else normalize(value)

            if not key:
                # 빈 키가 인덱스에 들어가면 모든 질문에 매칭되므로 조용히 넘기지 않는다
                raise ValueError(f"정규화하면 빈 값이 되는 별칭: entity_id={company.entity_id}, value={value!r}")

            if not is_hangul and len(key.replace(" ", "")) < min_alphanum_len:
                # 영문·숫자 초단문 (Micron "MU" 등)은 다른 단어 안에서 걸리는 오탐이 커서 뺀다
                logger.info("초단문 별칭 제외: entity_id=%s, value=%r", company.entity_id, value)
                continue

            if key in seen_keys:
                # 같은 회사 안의 중복은 정상 ("NVIDIA CORP"와 "NVIDIA CORP/CA"가 둘 다 "nvidia")
                continue
            seen_keys.add(key)

            owners_by_key[key].add(company.entity_id)
            candidates.append(
                AliasEntry(
                    entity_id=company.entity_id,
                    name=company.name,
                    alias=value,
                    key=key,
                    is_hangul=is_hangul,
                )
            )

    # ---- 2패스: 충돌 key 제외 ----
    # dict 컴프리헨션: {k: v for k, v in ... if 조건} 으로 조건에 맞는 항목만 새 dict로
    conflicts = {key: owners for key, owners in owners_by_key.items() if len(owners) > 1}
    for key, owners in conflicts.items():
        logger.warning("별칭 충돌로 인덱스에서 제외: key=%r, entity_ids=%s", key, sorted(owners))

    # 제너레이터 표현식을 tuple()로 바로 감쌈: 리스트를 중간에 만들지 않음
    entries = tuple(entry for entry in candidates if entry.key not in conflicts)
    return AliasIndex(entries=entries)
