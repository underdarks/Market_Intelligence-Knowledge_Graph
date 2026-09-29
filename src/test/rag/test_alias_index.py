# test/rag/entity_linking/test_alias_index.py
import pytest

from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import (
    AliasConflictError,
    CompanyRecord,
    build_alias_index,
)


def company(entity_id, name, aliases=(), tickers=(), former_names=()):
    return CompanyRecord(entity_id, name, tuple(aliases), tuple(tickers), tuple(former_names))


def keys(index):
    return {e.key for e in index.entries}


def test_name_derived():
    # 1. name에서 유도: "삼성전자(주)" -> "삼성전자"
    index = build_alias_index([company("dart:1", "삼성전자(주)")])
    assert keys(index) == {"삼성전자"}


def test_tickers_included():
    # 2. tickers도 인덱스에 들어간다
    index = build_alias_index(
        [company("cik:1", "NVIDIA CORP", tickers=["NVDA"]), company("dart:1", "삼성전자(주)", tickers=["005930"])]
    )
    assert {"nvda", "005930"} <= keys(index)


def test_short_alphanum_excluded_but_short_hangul_kept():
    # 3. 영문 초단문 티커 "MU"는 제외, 한글 "삼전"(2자)은 유지
    index = build_alias_index(
        [company("cik:1", "MICRON TECHNOLOGY INC", tickers=["MU"]), company("dart:1", "삼성전자(주)", aliases=["삼전"])]
    )
    assert "mu" not in keys(index)
    assert "삼전" in keys(index)


def test_same_company_duplicate_is_one_entry():
    # 4. 같은 회사 안에서 name과 former_names가 같은 키가 되는 건 정상 (1건만)
    index = build_alias_index([company("cik:1", "NVIDIA CORP", former_names=["NVIDIA CORP/CA"])])
    assert [e.key for e in index.entries] == ["nvidia"]


def test_conflict_between_companies():
    # 5. 다른 회사가 같은 별칭이면 기동 실패
    with pytest.raises(AliasConflictError):
        build_alias_index(
            [
                company("dart:1", "가나다(주)", aliases=["공용별칭"]),
                company("dart:2", "라마바(주)", aliases=["공용별칭"]),
            ]
        )


def test_empty_key_raises():
    # 6. 정규화하면 사라지는 별칭은 실패 ("(주)"만 남음)
    with pytest.raises(ValueError):
        build_alias_index([company("dart:1", "삼성전자(주)", aliases=["(주)"])])


def test_hangul_key_is_squashed():
    # 7. 한글 별칭은 공백을 지운 키: "SK 하이닉스"와 "SK하이닉스"는 같은 키 (1건)
    index = build_alias_index([company("dart:1", "SK하이닉스", aliases=["SK 하이닉스"])])
    assert [e.key for e in index.entries] == ["sk하이닉스"]
