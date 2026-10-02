# 잠정: C1(Entity Linking) 구현 시 회사 메타데이터 기반으로 교체하고 이 매핑은 삭제한다.
# 인덱싱 쪽 언어 판별 규칙과 지금은 이중으로 존재하는 상태라서 C1에서 한 곳으로 합쳐야 한다.

import asyncio
import logging
from typing import AsyncGenerator

from market_intelligence_knowledge_graph.rag.classification.classfier import QuestionClassifier
from market_intelligence_knowledge_graph.rag.classification.planner import (
    ClarifyPlan,
    Plan,
    RetrievePlan,
    RoutePlanner,
    DeclinePlan,
)
from market_intelligence_knowledge_graph.rag.schemas.answer_event import (
    AnswerEvent,
    ClarificationCandidate,
    ClarificationEvent,
    ClarifyReason,
    CorrectedEntity,
    DeclineEvent,
    DeclineReason,
    DoneEvent,
    EntityCorrectionEvent,
)
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import LinkResult, MatchedBy
from market_intelligence_knowledge_graph.rag.entity_linking.linker import EntityLinker
from market_intelligence_knowledge_graph.rag.generation.answer_generator import generate_answer
from market_intelligence_knowledge_graph.rag.retrieve.retriever import Retriever
from market_intelligence_knowledge_graph.rag.retrieve.schema.schema import RetrievalQuery
from market_intelligence_knowledge_graph.rag.schemas.answer_request import AnswerRequest

# 되묻기 문구. 사용자 노출 문구라 한 곳에 모아둠 (다국어 붙으면 리소스 파일로 이동)
_CLARIFY_MESSAGES: dict[ClarifyReason, str] = {
    ClarifyReason.NOT_FOUND: "어느 회사에 대한 질문인지 찾지 못했어요. 회사명을 넣어 다시 질문해 주세요.",
    ClarifyReason.AMBIGUOUS: "어느 회사를 말씀하신 건가요?",
    ClarifyReason.MULTIPLE_UNSUPPORTED: "지금은 한 번에 한 회사씩 답할 수 있어요. 어느 회사부터 볼까요?",
}

# 답변 거절
_DECLINE_MESSAGES: dict[DeclineReason, str] = {
    DeclineReason.INVESTMENT_ADVICE: "매수·매도 추천이나 가격 예측은 드리지 않아요. 판단에 필요한 근거와 데이터는 찾아드릴 수 있어요.",
    DeclineReason.OUT_OF_SCOPE: "투자·기업 분석과 관련된 질문에 답할 수 있어요.",
    DeclineReason.NOT_SUPPORTED_YET: "이 유형의 질문은 준비 중이에요. 지금은 기업 이벤트·실적 요약과 원인 분석을 지원해요.",
}

log = logging.getLogger(__name__)


class RagService:
    """오케스트레이터: 분류 -> 링킹 -> 경로 결정 -> 검색 -> 생성

    상태 없는 싱글톤: 요청별 값은 절대 self에 저장하지 않는다.
    """

    def __init__(
        self,
        classifier: QuestionClassifier,
        linker: EntityLinker,
        retrievers: list[Retriever],
        route_planner: RoutePlanner,
    ) -> None:
        self._classifier = classifier
        self._linker = linker
        self._route_planner = route_planner
        self._retrievers: dict[str, Retriever] = {}

        for retriever in retrievers:
            if retriever.name in self._retrievers:  # 해당 키가 딕셔너리에 존재하는지 확인
                raise ValueError(f"검색기 이름 중복: {retriever.name}")
            self._retrievers[retriever.name] = retriever

    def _clarify_message(self, reason: ClarifyReason, unresolved: tuple[str, ...]) -> str:
        # 못 찾은 회사명이 있으면 문구에 넣어서, 사용자가 뭘 고쳐야 할지 알게 함
        if reason is ClarifyReason.NOT_FOUND and unresolved:
            names = ", ".join(f"'{name}'" for name in unresolved)
            return f"{names}은(는) 아직 지원하지 않거나 찾지 못한 회사예요. 회사명을 확인해 다시 질문해 주세요."

        return _CLARIFY_MESSAGES[reason]

    def _describe_plan(self, plan: Plan) -> str:
        """plan -> 로그용 한 줄 요약. 순수 포맷 변환이라 함수 (A-8)."""
        match plan:
            case RetrievePlan(retriever_names=names, entity=entity):
                return (
                    f"retrieve retrievers={list(names)} "
                    f"entity={entity.entity_id}({entity.name}) matched_by={entity.matched_by.value}"
                )
            case ClarifyPlan(reason=reason, candidates=candidates):
                return f"clarify reason={reason.value} candidates={[c.entity_id for c in candidates]}"
            case DeclinePlan(reason=reason):
                return f"decline reason={reason.value}"
            case _:
                return type(plan).__name__  # 새 Plan 타입이 생겨도 로그는 안 깨지게

    async def response_answer_stream(self, req: AnswerRequest) -> AsyncGenerator[AnswerEvent, None]:
        """사용자 질문(프롬프트)를 스트림 형식으로 답변한다.

            selected_entity_ids: 되묻기 후 사용자가 선택한 회사 id들
        Yields:
            되묻기: ClarificationEvent -> DoneEvent
            답변:   SourcesEvent -> TokenEvent x N -> DoneEvent (generate_answer가 순서 보장)
        """

        question = req.question

        # 1. 질문 분류
        classification: Classification = await self._classifier.classify(question=question)

        # 2. 링킹(사용자 선택이 있으면 질문 매칭을 건너뛰고 그 ID로 확정)
        if req.selected_entity_ids:
            link_result: LinkResult = await self._linker.resolve_ids(entity_ids=req.selected_entity_ids)

        else:
            link_result: LinkResult = await self._linker.link(question=question)

        # 3. 라우팅을 위한 응답 분류
        plan: Plan = self._route_planner.plan(classification=classification, link_result=link_result)

        # 4. 판단 근거 로그: 거절·되묻기 비율, 보정 비율, 오링킹 추적의 원천 데이터
        log.info(
            # 인접한 문자열 리터럴은 자동으로 이어 붙음: 한 레코드 안에서 줄만 바꿈
            "route\n"
            "  request  : level=%s\n"
            "  classify : type=%s conf=%.2f mentions=%s\n"
            "  link     : status=%s entities=%s matched_by=%s unresolved=%s\n"
            "  plan     : %s",
            req.level.value,
            classification.type.value,
            classification.confidence,
            # 추가: LLM이 뽑은 언급 (C1-15부터 의미 있음). 지금 스텁은 빈 목록
            [(m.surface, m.guess) for m in classification.mentions],
            link_result.status.value,
            link_result.company_ids,
            [e.matched_by.value for e in link_result.entities],
            link_result.unresolved_mentions,
            self._describe_plan(plan),  # 추가: 경로 결정 상세
        )

        # 5. 라우팅
        match plan:
            # 답변 안하는 케이스
            case DeclinePlan(reason=reason):
                yield DeclineEvent(reason=reason, message=_DECLINE_MESSAGES[reason])
                yield DoneEvent()
                return  # 검색·LLM 호출 없음

            # 되묻기 케이스
            case ClarifyPlan(candidates=candidates, reason=reason):
                yield ClarificationEvent(
                    reason=reason,
                    message=self._clarify_message(reason, link_result.unresolved_mentions),
                    candidates=[ClarificationCandidate(entity_id=e.entity_id, name=e.name) for e in candidates],
                )
                yield DoneEvent()  # 되묻기도 Done으로 끝냄 (DoneEvent 필수 필드 있으면 맞춰서)
                return  # 제너레이터 종료(검색·LLM 호출 없음)

            # 답변 케이스
            case RetrievePlan(retriever_names=names, entity=entity):
                # LLM이 오타·별명을 보정해 확정했으면 답변 전에 알림
                if entity.matched_by is MatchedBy.LLM_GUESS:
                    yield EntityCorrectionEvent(
                        corrections=[
                            CorrectedEntity(surface=entity.matched_alias, entity_id=entity.entity_id, name=entity.name)
                        ]
                    )

                query = RetrievalQuery(question=question, entity_id=entity.entity_id)
                retrievers = [self._retrievers[name] for name in names]  # 없는 이름이면 KeyError 그대로 올림

                # 병렬 실행. 결과는 넘긴 순서대로 돌아옴 = [출처 n] 번호 순서
                # asyncio.gather는 여러 개의 비동기(async) 작업(코루틴)을 동시에(병렬로) 실행하고, 그 결과를 한 번에 묶어서 받아오는 함수
                results = await asyncio.gather(*(r.retrieve(query) for r in retrievers))

                items = [
                    item for result in results for item in result
                ]  # 2중 for문을 통한 평탄화: [[a, b], [c]] -> [a, b, c]

                async for event in generate_answer(question, items):  # 답변 생성
                    yield event

            case _:
                # Plan에 새 타입이 추가됐는데 분기를 안 만든 경우 즉시 실패 (Java sealed switch의 누락 검사 역할)
                raise TypeError(f"처리하지 않은 Plan 타입: {type(plan).__name__}")
