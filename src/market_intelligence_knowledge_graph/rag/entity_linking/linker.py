import logging
from typing import Protocol
from market_intelligence_knowledge_graph.rag.classification.schemas.schema import ExtractedMention
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import (
    LinkResult,
    LinkStatus,
    LinkedEntity,
    MatchedBy,
)
from market_intelligence_knowledge_graph.rag.entity_linking.matcher import match, status_for_count
from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import AliasIndex
from market_intelligence_knowledge_graph.rag.entity_linking.normalizer import squash

log = logging.getLogger(__name__)


# Protocol은 덕타이핑으로, java의 interface와 동일하지만 구현체는 implements를 안 적어고 메서드 구현하면됨
# 자바 컴파일러 같은 타입 검사기(mypy)는 알아서 인터페이스를 구현했다고 인정해 주는 스마트한 타입
class EntityLinker(Protocol):
    """
    질문에서 회사를 찾는 공통 인터페이스. RagService는 이것만 안다.
    지금 구현은 메모리 조회라 async가 필요 없지만, LLM 폴백이 붙어도 호출부가 안 바뀌게 처음부터 async로 맞춘다.
    """

    async def link(self, question: str) -> LinkResult: ...
    async def resolve_ids(self, entity_ids: tuple[str, ...]) -> LinkResult: ...


# EntityLinker Protocol 구현체. async는 Protocol 계약용이고 실제 일은 match()가 함.
class DictionaryEntityLinker:
    def __init__(self, index: AliasIndex) -> None:
        self._index = index
        # ID -> 정식명. resolve_ids의 카탈로그 검증용 (같은 회사 항목이 여러 개라 dict가 중복 제거)
        self._names_by_id: dict[str, str] = {e.entity_id: e.name for e in index.entries}

    async def resolve_ids(self, entity_ids: tuple[str, ...]) -> LinkResult:
        """되묻기 후 사용자가 고른 ID -> LinkResult. 카탈로그에 없는 ID는 버리고 경고."""
        entities: list[LinkedEntity] = []
        for entity_id in dict.fromkeys(entity_ids):  # dict.fromkeys: 순서 유지하며 중복 제거
            name = self._names_by_id.get(entity_id)
            if name is None:
                log.warning("카탈로그에 없는 선택 ID 무시: %r", entity_id)
                continue
            entities.append(
                LinkedEntity(entity_id=entity_id, name=name, matched_alias=name, matched_by=MatchedBy.USER_SELECTED)
            )
        entities.sort(key=lambda e: e.entity_id)

        if not entities:
            status = LinkStatus.NOT_FOUND
        elif len(entities) == 1:
            status = LinkStatus.CONFIRMED
        else:
            status = LinkStatus.MULTIPLE
        return LinkResult(status=status, entities=tuple(entities))

    async def link(self, question: str, mentions: tuple[ExtractedMention, ...] = ()) -> LinkResult:
        """mentions(LLM 추출)가 있으면 언급 단위로, 없으면 질문 전체로 매칭."""
        # 1. mentions 없음(스텁 분류기, LLM 실패): C1-8과 동일한 질문 전체 매칭
        if not mentions:
            return match(self._index, question)

        question_key = squash(question)  # 원문 존재 검증용 (공백·대소문자 무시)
        adopted: dict[str, LinkedEntity] = {}  # entity_id -> 확정된 회사
        ambiguous: dict[str, LinkedEntity] = {}  # entity_id -> 모호 후보
        unresolved: list[str] = []  # 사전에서 못 찾은 언급 원문

        for mention in mentions:
            # 2. 환각 차단: 질문에 실제로 없는 surface는 버림
            surface_key = squash(mention.surface)
            if not surface_key or surface_key not in question_key:
                log.warning("질문에 없는 언급 무시: surface=%r", mention.surface)
                continue

            # 3. surface 그대로 사전 매칭 (가장 신뢰도 높음)
            by_surface = match(self._index, mention.surface)
            if by_surface.entities:
                for entity in by_surface.entities:
                    # 대입(=): 같은 회사가 앞서 LLM_GUESS로 들어왔어도 ALIAS로 덮어씀 (ALIAS 우선)
                    adopted[entity.entity_id] = entity
                continue

            # 4. surface 실패 시 guess(LLM 추정 정식명)로 매칭
            if mention.guess:
                by_guess = match(self._index, mention.guess)
                if len(by_guess.entities) == 1:
                    # frozen 모델이라 수정 불가: model_copy(update=...)로 일부 필드만 바꾼 복사본 생성
                    guessed = by_guess.entities[0].model_copy(
                        update={"matched_by": MatchedBy.LLM_GUESS, "matched_alias": mention.surface}
                    )
                    # setdefault: 이미 있으면(ALIAS로 확정) 유지, 없을 때만 추가
                    adopted.setdefault(guessed.entity_id, guessed)
                    continue
                if len(by_guess.entities) >= 2:
                    # guess 하나가 여러 회사에 걸림 -> 사용자에게 선택 요청
                    for entity in by_guess.entities:
                        ambiguous.setdefault(entity.entity_id, entity)
                    continue

            # 5. surface, guess 모두 실패
            unresolved.append(mention.surface)

        # 6. 상태 판정
        if ambiguous:
            # 확정 회사 + 모호 후보를 함께 보여주고 고르게 함. {**a, **b}: 뒤쪽(adopted) 값이 우선
            merged = {**ambiguous, **adopted}
            entities = tuple(sorted(merged.values(), key=lambda e: e.entity_id))
            status = LinkStatus.AMBIGUOUS
        else:
            entities = tuple(sorted(adopted.values(), key=lambda e: e.entity_id))
            status = status_for_count(len(entities))

        # 7. 측정용: 질문 전체 사전 매칭과 결과가 다르면 기록 (LLM 누락·과추출 추적)
        dict_ids = set(match(self._index, question).company_ids)
        llm_ids = {e.entity_id for e in entities}
        if dict_ids != llm_ids:
            log.info("LLM 추출과 사전 매칭 불일치: llm=%s dict=%s", sorted(llm_ids), sorted(dict_ids))

        return LinkResult(status=status, entities=entities, unresolved_mentions=tuple(unresolved))
