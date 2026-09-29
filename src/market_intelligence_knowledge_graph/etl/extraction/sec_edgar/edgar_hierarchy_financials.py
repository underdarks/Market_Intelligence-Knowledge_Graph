from edgar import Company, set_identity

from market_intelligence_knowledge_graph.config.config import SEC_IDENTITY
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_financials import get_edgar_financials

# statement_type별로 각각 캐싱 (BalanceSheet, IncomeStatement, CashFlow 등)
_hierarchy_template_cache = {}


# 계층 트리를 재귀로 순회하면서 실제 값이 있는 리프 노드만 수집
def _collect_leaves(item, leaves: list) -> None:
    if not item.is_abstract and item.concept is not None:
        leaves.append(item)
    for child in item.children:
        _collect_leaves(child, leaves)


# get_structured_statement()로 concept별 계층 정보(depth, is_total) 템플릿을 만듦
# 다만, "재무제표 본문 대표 항목"만 커버하고 "세부 주석 항목"은 커버 못함
def _build_hierarchy_template(ticker: str, statement_type: str = "BalanceSheet") -> dict:

    c = Company(ticker)
    """
    get_facts()
      → 회사의 모든 XBRL 값을 "평평한 목록"으로 줌 (27,281개, 순서·계층 없음)
      → 재무상태표 항목, 손익계산서 항목, 심지어 임원보수(ecd:) 항목까지 다 섞여 있음
      → "이 회사의 모든 재무 관련 사실들을 모아둔 창고"에 가까움

    get_structured_statement("BalanceSheet")
      → "재무상태표"라는 하나의 완성된 문서 형태로 정리해서 줌
      → ASSETS > Current assets: > Cash and Cash Equivalents... 처럼
        실제 재무제표 문서를 펼쳤을 때 보이는 순서·계층 그대로 재현
      → "창고에서 재무상태표에 해당하는 것만 골라 정리된 서류철로 만들어준 것"
    """

    stmt = c.get_structured_statement(statement_type)

    leaves = []
    for item in stmt.items:
        _collect_leaves(item, leaves)

    template = {}
    for leaf in leaves:
        template[leaf.concept] = {
            "depth": leaf.depth,
            "is_total": leaf.is_total,
        }

    return template


# statement_type별로 캐싱된 계층 템플릿을 반환. 없으면 API 호출해서 새로 만듦
def get_hierarchy_template(ticker: str, statement_type: str) -> dict:
    key = f"{ticker}:{statement_type}"

    if key not in _hierarchy_template_cache:
        _hierarchy_template_cache[key] = _build_hierarchy_template(ticker, statement_type)

    return _hierarchy_template_cache[key]


if __name__ == "__main__":
    set_identity(SEC_IDENTITY)
    c = Company("NVDA")
    records = get_edgar_financials("NVDA")

    # 재고자산(하위 세부 항목 확인)
    inv_items = [r for r in records if "Inventory" in r["concept"]]
    print(f"총 {len(inv_items)}건")

    unique_concepts = sorted(set(r["concept"] for r in inv_items))
    for c in unique_concepts:
        print(c)
