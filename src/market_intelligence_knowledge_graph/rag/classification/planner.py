from dataclasses import dataclass
from enum import Enum

from market_intelligence_knowledge_graph.rag.schemas.answer_event import ClarifyReason, DeclineReason
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification, QuestionType
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import LinkResult, LinkStatus, LinkedEntity
from market_intelligence_knowledge_graph.rag.retrieve.filing_chunk_retriever import FilingChunkRetriever


@dataclass(frozen=True)
class RetrievePlan:
    """검색 진행. 어떤 검색기를, 어느 회사로."""

    retriever_names: tuple[str, ...]  # 실행할 검색기 이름. 이 순서가 [출처 n] 번호 순서가 됨
    entity: LinkedEntity  # MVP는 단일 회사 (Fan-out 붙으면 tuple로 확장)


@dataclass(frozen=True)
class ClarifyPlan:
    """검색하지 않고 되묻기로 종료."""

    reason: ClarifyReason
    candidates: tuple[LinkedEntity, ...]  # 되묻기 화면에 보여줄 회사들 (NOT_FOUND면 빈 tuple)


@dataclass(frozen=True)
class DeclinePlan:
    """답변 안 함 (거절 또는 준비 중)."""

    reason: DeclineReason


# 결과 타입: 둘 중 하나 (Java의 sealed interface + record 조합과 같은 용도)
Plan = RetrievePlan | ClarifyPlan | DeclinePlan

# 유형별 거절 사유. 여기 없는 유형은 지원 대상(T1, T2)
_DECLINE_BY_TYPE: dict[QuestionType, DeclineReason] = {
    QuestionType.T7: DeclineReason.INVESTMENT_ADVICE,
    QuestionType.T8: DeclineReason.OUT_OF_SCOPE,
    QuestionType.T4: DeclineReason.NOT_SUPPORTED_YET,  # 정형 지표 검색기 붙으면 삭제
    QuestionType.T5: DeclineReason.NOT_SUPPORTED_YET,
    QuestionType.T6: DeclineReason.NOT_SUPPORTED_YET,  # 폴백 생성기 붙으면 삭제
    QuestionType.T9: DeclineReason.NOT_SUPPORTED_YET,
    QuestionType.T10: DeclineReason.NOT_SUPPORTED_YET,
}


class RoutePlanner:
    """분류 x 링킹 -> 처리 경로. 설정값(신뢰도 하한)을 가지므로 클래스로 두고 주입한다."""

    def __init__(self, min_confidence: float) -> None:
        self._min_confidence = min_confidence  # 최소 분류 신뢰도

    # 응답 유형 분류
    def plan(self, classification: Classification, link_result: LinkResult) -> Plan:
        # 1. 저신뢰도는 T1로 간주. 거절 판정보다 먼저 해야 애매한 T7 판정으로 정상 질문을 막지 않음
        effective_type = classification.type if classification.confidence >= self._min_confidence else QuestionType.T1

        # 2. 거절·준비 중: 링크 상태보다 먼저 (회사를 되묻고 나서 거절하는 UX 방지)
        decline_reason = _DECLINE_BY_TYPE.get(effective_type)  # dict.get: 없으면 None
        if decline_reason is not None:
            return DeclinePlan(reason=decline_reason)

        # 3. 지원 유형(T1, T2): 링크 상태로 분기
        match link_result.status:
            case LinkStatus.NOT_FOUND:
                return ClarifyPlan(reason=ClarifyReason.NOT_FOUND, candidates=())
            case LinkStatus.AMBIGUOUS:
                return ClarifyPlan(reason=ClarifyReason.AMBIGUOUS, candidates=link_result.entities)
            case LinkStatus.MULTIPLE:
                return ClarifyPlan(reason=ClarifyReason.MULTIPLE_UNSUPPORTED, candidates=link_result.entities)
            case LinkStatus.CONFIRMED:
                return RetrievePlan(retriever_names=(FilingChunkRetriever.name,), entity=link_result.entities[0])
        raise ValueError(f"처리하지 않은 링크 상태: {link_result.status}")
