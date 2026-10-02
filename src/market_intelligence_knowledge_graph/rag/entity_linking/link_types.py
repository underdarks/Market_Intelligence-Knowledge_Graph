from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class MatchedBy(str, Enum):
    """회사를 어떻게 확정했는지. 알림 이벤트 여부와 정밀도 측정에 쓴다."""

    ALIAS = "alias"  # 사전 별칭 정확 매칭
    LLM_GUESS = "llm_guess"  # 오타·별명을 LLM이 추정, 그 추정명이 사전에 걸림 -> 알림 필요
    USER_SELECTED = "user_selected"  # 되묻기 후 사용자가 직접 고름


# 링킹 결과 상태. Enum: 정해진 값만 허용하는 타입 (Java의 enum과 동일)
class LinkStatus(str, Enum):
    CONFIRMED = "confirmed"  # 기존: 서로 다른 회사 1개 확정(ex. 삼전 실적)
    MULTIPLE = "multiple"  # 서로 다른 회사 2개 이상, 각각 확정(ex. 삼전 하닉 매출 비교)
    AMBIGUOUS = "ambiguous"  # 기존: 한 언급이 여러 후보에 걸림(ex. 삼성 매출시 삼성전자인지 삼성전기인지 등)
    NOT_FOUND = "not_found"  # 매칭 없음(ex. 반도체 업활)


# 링킹된 회사 1개
class LinkedEntity(BaseModel):
    # Pydantic에서 불변은 데코레이터가 아니라 설정으로: 생성 후 필드 변경 금지 + 해시 가능
    model_config = ConfigDict(frozen=True)

    entity_id: str  # 회사 식별자 (예: "dart:00126380"). 검색 필터·그래프 조회 키
    name: str  # 정식명 (예: "삼성전자(주)"). 프롬프트·화면 표시용
    matched_alias: str  # 질문에서 실제로 걸린 별칭 원문 (예: "삼전"). 되묻기 문구·디버깅용
    matched_by: MatchedBy = MatchedBy.ALIAS  # 기본값: 기존 matcher 코드 수정 없이 호환


# 상태별 허용 entities 개수. 모듈 상수로 빼서 검증할 때마다 dict를 새로 만들지 않음
# key를 문자열이 아닌 Enum 멤버로: Enum 정의가 바뀌어도 오타·불일치가 정적으로 드러남
_ENTITY_COUNT_RULES = {
    LinkStatus.CONFIRMED: lambda n: n == 1,
    LinkStatus.MULTIPLE: lambda n: n >= 2,
    LinkStatus.AMBIGUOUS: lambda n: n >= 2,
    LinkStatus.NOT_FOUND: lambda n: n == 0,
}


# match() / EntityLinker.link() 반환 타입
class LinkResult(BaseModel):

    model_config = ConfigDict(frozen=True)

    status: LinkStatus
    # tuple: frozen이어도 list는 append로 내부 변경이 가능해서 불변식이 깨질 수 있음
    # JSON 직렬화 시에는 배열로 나감
    entities: tuple[LinkedEntity, ...]  # entity_id 순 정렬
    unresolved_mentions: tuple[str, ...] = ()  # LLM이 뽑았지만 사전에 없는 언급 (되묻기 문구)

    # mode="after": 필드 타입 검증이 끝난 뒤 실행 (status가 이미 LinkStatus로 변환된 상태)
    @model_validator(mode="after")
    def _check_invariant(self) -> "LinkResult":
        """status와 entities 개수의 정합성 검증. 틀린 결과 객체가 생성되는 것 자체를 막는다."""
        rule = _ENTITY_COUNT_RULES[self.status]
        if not rule(len(self.entities)):
            raise ValueError(f"status={self.status.value}와 entities {len(self.entities)}건이 맞지 않습니다")
        return self

    @property  # 계산 속성: result.company_ids (괄호 없이). 직렬화 대상 아님
    def company_ids(self) -> tuple[str, ...]:
        """ID만 필요한 곳(검색 필터, 테스트 assert)용 편의 속성."""
        return tuple(e.entity_id for e in self.entities)
