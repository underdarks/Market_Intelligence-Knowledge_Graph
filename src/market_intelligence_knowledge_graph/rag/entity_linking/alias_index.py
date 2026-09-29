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


def build_alias_index(companies: list[CompanyRecord]) -> AliasIndex:
    """
    회사 목록으로 별칭 인덱스를 만든다.

    Raises:
        AliasConflictError: 서로 다른 회사가 같은 정규화 키를 가질 때
        ValueError: 정규화하면 빈 문자열이 되는 값이 있을 때 (예: 별칭이 "(주)")
    """
    owner_by_key: dict[str, str] = {}  # 정규화 키 -> 그 키를 처음 가져간 entity_id
    entries: list[AliasEntry] = []

    for company in companies:
        # name을 맨 앞에 둔다. 같은 회사에서 key가 겹치면 먼저 나온 원문이 남는데,
        # 그 원문이 되묻기 화면의 matched_alias로 나가므로 정식명이 남게 하려는 것.
        # name, tickers, former_names는 aliases에 복사돼 있지 않아서 여기서 직접 모은다.
        values = (company.name, *company.aliases, *company.tickers, *company.former_names)

        for value in values:
            is_hangul = bool(_HANGUL.search(value))
            # 한글은 공백을 지운 키(부분 문자열 매칭용), 영문·숫자는 공백을 유지한 키(단어 경계 매칭용)
            key = squash(value) if is_hangul else normalize(value)

            if not key:
                # "(주)"처럼 정규화하면 사라지는 값. 빈 키가 인덱스에 들어가면 모든 질문에 매칭되므로 조용히 넘기지 않고 원인을 바로 찾게 실패시킨다.
                raise ValueError(f"정규화하면 빈 값이 되는 별칭: entity_id={company.entity_id}, value={value!r}")

            if not is_hangul and len(key.replace(" ", "")) < MIN_ALPHANUM_ALIAS_LENGTH:
                # 영문·숫자 초단문 (Micron 티커 "MU" 등)은 다른 단어 안에서 걸리는 오탐이 커서 뺀다.
                logger.info("초단문 별칭 제외: entity_id=%s, value=%r", company.entity_id, value)
                continue

            owner = owner_by_key.get(key)
            if owner is None:
                owner_by_key[key] = company.entity_id
            elif owner != company.entity_id:
                # 서로 다른 회사가 같은 키: 요청 중에 조용히 한쪽으로 확정되는 게 가장 위험해서
                # 기동 시점에 서버를 못 뜨게 막는다.
                raise AliasConflictError(f"별칭 충돌: key={key!r}, entity_id={owner} vs {company.entity_id}")
            else:
                # 같은 회사 안의 중복은 정상이다. name "NVIDIA CORP"와
                # former_names "NVIDIA CORP/CA"가 둘 다 "nvidia"가 되는 경우.
                continue

            entries.append(
                AliasEntry(
                    entity_id=company.entity_id,
                    name=company.name,
                    alias=value,
                    key=key,
                    is_hangul=is_hangul,
                )
            )

    return AliasIndex(entries=tuple(entries))
