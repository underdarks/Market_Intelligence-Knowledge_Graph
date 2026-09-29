from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

LinkStatus = Literal["confirmed", "ambiguous", "not_found"]


# LinkedEntity: 매칭된 단일 엔티티(회사 등) 정보를 담는 데이터 모델
class LinkedEntity(BaseModel):
    entity_id: str  # 엔티티의 고유 식별자 (예: DB의 Primary Key, Neo4j ID 등)
    name: str  # 화면 표시용 대표 이름 (예: Neo4j Company 노드의 정식 명칭 '삼성전자')

    matched_alias: str  # 유저 질문/문장에서 실제 링킹(매칭)에 사용된 단어/별칭
    # (예: 질문에 '삼전'이라고 입력되었다면 name='삼성전자', matched_alias='삼전'으로 저장)
    # 💡 용도: 시스템 로그 기록 및 "혹시 '삼전'을 의미하신 건가요?" 같은 사용자 확인(되묻기) 화면의 근거 자료로 활용됨


# LinkResult: 링킹 결과 전체 상태 및 엔티티 목록을 관리하는 데이터 모델
class LinkResult(BaseModel):
    status: LinkStatus  # 링킹 결과 상태값 (예: Enum 형태의 CONFIRMED, AMBIGUOUS, NOT_FOUND 등)
    entities: list[LinkedEntity]  # 매칭된 LinkedEntity 객체들의 리스트

    # Pydantic v2의 모델 단위 검증 데코레이터
    # mode="after": 필드들의 기본 타입 검사가 끝난 "후"에 이 검증 함수를 실행함
    @model_validator(mode="after")
    def _check_invariant(self) -> "LinkResult":
        """[도메인 불변성(Invariant) 검증 함수]

        상태값(status)과 entities의 개수(len) 간의 정합성을 검증합니다.
        불완전하거나 조건에 맞지 않는 객체가 생성되는 것을 사전에 차단합니다.
        """

        # 각 status별로 허용되는 entities 개수의 조건을 람다(lambda) 함수로 정의한 딕셔너리
        expected = {
            "confirmed": lambda n: n == 1,  # 'confirmed' : 반드시 1개만 매칭되어야 함 (단일 확정)
            "ambiguous": lambda n: n >= 2,  # 'ambiguous' : 2개 이상 매칭되어 모호한 상태 (후보군 제시)
            "not_found": lambda n: n == 0,  # 'not_found' : 매칭된 엔티티가 없어야 함 (0개)
        }

        # 1. 현재 객체의 status(self.status)에 해당하는 검증 람다 함수를 가져와서,
        # 2. actual entities 개수(len(self.entities))를 넣어 조건을 만족하는지(True/False) 확인합니다.
        if not expected[self.status](len(self.entities)):
            # 조건이 불일치하면 예외(ValueError)를 발생시켜 잘못된 데이터 생성을 방지합니다.
            raise ValueError(f"status={self.status!r}와 entities {len(self.entities)}건이 맞지 않습니다")

        # 검증을 통과한 정상 객체(self)를 그대로 반환합니다.
        return self
