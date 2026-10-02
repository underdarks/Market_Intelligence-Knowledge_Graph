"""DictionaryEntityLinker의 mentions 링킹과 resolve_ids 단위 테스트 (DB 없이 가짜 회사 인덱스)."""

import asyncio

import pytest

from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification, ExtractedMention, QuestionType
from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import CompanyRecord, build_alias_index
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import LinkResult, LinkStatus, LinkedEntity, MatchedBy
from market_intelligence_knowledge_graph.rag.entity_linking.linker import DictionaryEntityLinker

# LinkStatus, MatchedBy: C1-1 DTO 경로로 import

COMPANIES = [
    CompanyRecord(entity_id="t:samsung", name="삼성전자(주)", aliases=("삼전",), tickers=(), former_names=()),
    CompanyRecord(entity_id="t:emech", name="삼성전기(주)", aliases=(), tickers=(), former_names=()),
    CompanyRecord(entity_id="t:hynix", name="SK하이닉스(주)", aliases=("하닉",), tickers=(), former_names=()),
    CompanyRecord(entity_id="t:micron", name="Micron Technology", aliases=("마이크론",), tickers=(), former_names=()),
]


@pytest.fixture(scope="module")
def linker() -> DictionaryEntityLinker:
    return DictionaryEntityLinker(index=build_alias_index(COMPANIES, min_alphanum_len=3))


def m(surface: str, guess: str | None = None) -> ExtractedMention:
    """mention 생성 헬퍼."""
    return ExtractedMention(surface=surface, guess=guess)


def link(linker, question, *mentions):
    """async link()를 동기 테스트에서 실행."""
    return asyncio.run(linker.link(question, tuple(mentions)))


# ---- link(mentions) ----
def test_no_mentions_falls_back_to_full_match(linker) -> None:
    result = link(linker, "삼전 실적")
    assert result.company_ids == ("t:samsung",)


def test_surface_match_is_alias(linker) -> None:
    result = link(linker, "삼전 실적", m("삼전"))
    assert result.status is LinkStatus.CONFIRMED
    assert result.entities[0].matched_by is MatchedBy.ALIAS


def test_guess_match_marks_llm_guess(linker) -> None:
    result = link(linker, "마이크런 HBM 점유율", m("마이크런", guess="마이크론"))
    entity = result.entities[0]
    assert entity.entity_id == "t:micron"
    assert entity.matched_by is MatchedBy.LLM_GUESS
    assert entity.matched_alias == "마이크런"  # 알림 문구용: 사용자 원문(오타) 보존


def test_hallucinated_surface_ignored(linker) -> None:
    # 질문에 없는 회사를 LLM이 뽑은 경우: 버리고 미해결로도 안 셈
    result = link(linker, "반도체 업황", m("삼전"))
    assert result.status is LinkStatus.NOT_FOUND
    assert result.unresolved_mentions == ()


def test_unresolved_mention_recorded(linker) -> None:
    result = link(linker, "XYZ전자 실적", m("XYZ전자"))
    assert result.status is LinkStatus.NOT_FOUND
    assert result.unresolved_mentions == ("XYZ전자",)


def test_alias_beats_guess_for_same_company(linker) -> None:
    # 같은 회사가 별칭과 추정 양쪽으로 잡히면 신뢰도 높은 ALIAS로 남아야 함 (알림 안 나감)
    result = link(linker, "삼전 삼성전쟈", m("삼성전쟈", guess="삼성전자"), m("삼전"))
    assert result.company_ids == ("t:samsung",)
    assert result.entities[0].matched_by is MatchedBy.ALIAS


def test_two_mentions_multiple(linker) -> None:
    result = link(linker, "삼전이랑 하닉 비교", m("삼전"), m("하닉"))
    assert result.status is LinkStatus.MULTIPLE


def test_guess_hitting_two_companies_is_ambiguous(linker) -> None:
    # 인위적 케이스: guess 하나가 두 회사에 걸리는 분기 검증용
    result = link(linker, "삼성 실적", m("삼성", guess="삼성전자 삼성전기"))
    assert result.status is LinkStatus.AMBIGUOUS
    assert set(result.company_ids) == {"t:samsung", "t:emech"}


# ---- resolve_ids ----
def test_resolve_valid_id(linker) -> None:
    result = asyncio.run(linker.resolve_ids(("t:hynix",)))
    assert result.status is LinkStatus.CONFIRMED
    assert result.entities[0].matched_by is MatchedBy.USER_SELECTED


def test_resolve_unknown_id_ignored(linker) -> None:
    result = asyncio.run(linker.resolve_ids(("t:nope",)))
    assert result.status is LinkStatus.NOT_FOUND


def test_resolve_duplicate_ids_once(linker) -> None:
    result = asyncio.run(linker.resolve_ids(("t:hynix", "t:hynix")))
    assert result.company_ids == ("t:hynix",)
