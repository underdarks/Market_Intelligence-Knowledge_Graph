from enum import Enum
from typing import Literal
from pydantic import BaseModel

"""
오케스트레이션(RagService)과 생성(generate_answer)이 내보내는 이벤트 타입 정의.
- 전송 방식(SSE 등)과 무관하게 "무엇을 내보내는지"만 고정한다.
- C3는 event 필드 값을 SSE의 "event:" 줄로, 나머지를 "data:" JSON으로 포장만 한다.

스트림 순서 규칙 (모든 경로는 DoneEvent로 끝난다):
  답변:      [EntityCorrection] -> Sources -> Token x N -> Done
  검색 0건:  Sources(빈 목록) -> Token(안내 문구) -> Done   (LLM 호출 없음)
  되묻기:    Clarification -> Done                      (검색·LLM 호출 없음)
  거절/준비중: Decline -> Done                           (검색·LLM 호출 없음)
"""


# ======= 사유 코드 (API 계약) =======
# 프론트가 문구 대신 이 코드로 UI를 분기할 수 있게 enum으로 고정.
# str 상속: JSON 직렬화 시 "not_found" 같은 문자열로 나감
class ClarifyReason(str, Enum):
    """되묻는 이유. planner.py는 여기서 import해서 쓴다 (이벤트 스키마가 계약의 원본)."""

    NOT_FOUND = "not_found"  # 회사를 못 찾음 -> 회사명을 넣어 다시 질문 요청
    AMBIGUOUS = "ambiguous"  # 후보가 여럿 -> 사용자가 선택
    MULTIPLE_UNSUPPORTED = "multiple_unsupported"  # 회사 여러 개 -> Fan-out 전까지 한 회사씩


class DeclineReason(str, Enum):
    """답변하지 않는 이유."""

    INVESTMENT_ADVICE = "investment_advice"  # T7: 매수 추천·가격 예측
    OUT_OF_SCOPE = "out_of_scope"  # T8: 투자 무관
    NOT_SUPPORTED_YET = "not_supported_yet"  # 기능 준비 중 (T4~T6, T9, T10)


# ========== 답변 이벤트 ==========
class SourceItem(BaseModel):
    """답변 근거 1건. 프론트의 출처 카드 단위."""

    index: int  # 본문의 [1], [2] 마커와 1:1 대응 (1부터). build_context의 [출처 n]과 같은 순서
    doc_id: str  # OpenSearch 문서 ID. 원본 청크 추적·디버깅용
    entity_id: str  # 어느 회사의 근거인지. 회사명은 Neo4j가 SSOT라 표시 단계에서 매핑
    section_title: str  # 공시 섹션명. "어디서 나온 정보인지" 표시용
    content: str  # 청크 원문. 출처 카드 펼침용
    score: float  # 검색 관련도. UI 참고용, 프롬프트엔 안 넣음 (질문 간 비교 불가한 상대 점수)


class SourcesEvent(BaseModel):
    """근거 목록. 토큰보다 먼저 1번: 프론트가 카드를 먼저 그려야 [n] 마커를 바로 연결함."""

    # Literal: 이 필드는 "sources"만 허용. 오타를 타입 체크가 잡고, JSON 역파싱 때 클래스 판별 키가 됨
    event: Literal["sources"] = "sources"
    sources: list[SourceItem]


class TokenEvent(BaseModel):
    """LLM 토큰(텍스트 조각). 답변이 끝날 때까지 여러 번. 이어 붙이는 건 프론트 책임."""

    event: Literal["token"] = "token"
    text: str


class DoneEvent(BaseModel):
    """스트림 종료 신호. 모든 경로의 마지막에 1번.
    이게 있어야 프론트가 '정상 종료'와 '연결 끊김'을 구분함.
    토큰 사용량, finish_reason이 필요해지면 여기에 필드 추가."""

    event: Literal["done"] = "done"


# ========== 오케스트레이션 이벤트 ==========
class ClarificationCandidate(BaseModel):
    """되묻기 화면의 회사 후보 1개. LinkedEntity를 그대로 노출하지 않고 API 응답 목적으로 분리."""

    entity_id: str  # 사용자가 고르면 다음 요청의 selected_entity_ids로 돌려받는 값
    name: str  # 화면 표시용 정식명


class ClarificationEvent(BaseModel):
    """회사를 특정하지 못해 되묻는 이벤트. 뒤에 DoneEvent만 온다."""

    event: Literal["clarification"] = "clarification"
    reason: ClarifyReason
    message: str  # 사용자에게 보여줄 문구
    candidates: list[ClarificationCandidate]  # NOT_FOUND면 빈 목록, 나머지는 선택 버튼용


class DeclineEvent(BaseModel):
    """답변하지 않는 이유를 알리는 이벤트 (거절 또는 준비 중). 뒤에 DoneEvent만 온다."""

    event: Literal["decline"] = "decline"
    reason: DeclineReason
    message: str


class CorrectedEntity(BaseModel):
    """LLM이 오타·별명을 보정해서 인식한 회사 1건."""

    surface: str  # 사용자가 쓴 그대로 (예: "마이크런")
    entity_id: str
    name: str  # 인식한 정식명 (예: "Micron Technology")


class EntityCorrectionEvent(BaseModel):
    """'마이크런을 마이크론으로 인식했어요' 알림. 답변보다 먼저 나가서 틀린 회사로 인식됐으면 사용자가 바로 알아채게 함."""

    event: Literal["entity_correction"] = "entity_correction"
    corrections: list[CorrectedEntity]


# ========== 합집합 타입 ==========
AnswerEvent = SourcesEvent | TokenEvent | DoneEvent | ClarificationEvent | DeclineEvent | EntityCorrectionEvent
