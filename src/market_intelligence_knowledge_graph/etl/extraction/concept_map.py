# 정규화된 concept 이름을 키로, 매핑될 원본 이름들을 값으로 관리(우리가 정의한 공통 이름으로 변환하기 위한 사전)
# raw concept(EDGAR: "us-gaap:..."/"ifrs-full:...", DART: "ifrs-full_..."/한글 account_nm)


CONCEPT_MAP: dict[str, list[str]] = {
    # ── 재무상태표(BS) - 유동자산 ──
    "cash_and_equivalents": [
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        "ifrs-full:CashAndCashEquivalents",
        "ifrs-full_CashAndCashEquivalents",
        "현금및현금성자산",
    ],
    "accounts_receivable": [
        "us-gaap:AccountsReceivableNetCurrent",
        "ifrs-full:TradeAndOtherCurrentReceivables",
        "ifrs-full_TradeAndOtherCurrentReceivables",
        "매출채권",
    ],
    "inventory": [
        "us-gaap:InventoryNet",
        "ifrs-full:Inventories",
        "ifrs-full_Inventories",
        "재고자산",
    ],
    "inventory_finished_goods": [
        "us-gaap:InventoryFinishedGoods",
        "us-gaap:InventoryFinishedGoodsNetOfReserves",
    ],
    "inventory_work_in_process": [
        "us-gaap:InventoryWorkInProcess",
        "us-gaap:InventoryWorkInProcessNetOfReserves",
    ],
    "inventory_raw_materials": [
        "us-gaap:InventoryRawMaterials",
        "us-gaap:InventoryRawMaterialsNetOfReserves",
    ],
    "prepaid_expense": [
        "us-gaap:PrepaidExpenseCurrent",
        "선급비용",
    ],
    "total_current_assets": [
        "us-gaap:AssetsCurrent",
        "ifrs-full:CurrentAssets",
        "유동자산",
    ],
    # ── 재무상태표(BS) - 총계 ──
    "total_assets": [
        "us-gaap:Assets",
        "ifrs-full:Assets",
        "ifrs-full_Assets",
        "자산총계",
    ],
    "total_liabilities": [
        "us-gaap:Liabilities",
        "ifrs-full:Liabilities",
        "ifrs-full_Liabilities",
        "부채총계",
    ],
    "total_equity": [
        "us-gaap:StockholdersEquity",
        "ifrs-full:Equity",
        "ifrs-full_Equity",
        "자본총계",
    ],
    # ── 손익계산서(IS) ──
    "revenue": [
        "us-gaap:Revenues",
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "ifrs-full:Revenue",
        "ifrs-full_Revenue",
        "매출액",
    ],
    "cost_of_revenue": [
        "us-gaap:CostOfRevenue",
        "매출원가",
    ],
    "gross_profit": [
        "us-gaap:GrossProfit",
        "매출총이익",
    ],
    "sg_and_a_expense": [
        "us-gaap:SellingGeneralAndAdministrativeExpense",
        "판매비와관리비",
    ],
    "research_and_development_expense": [
        "us-gaap:ResearchAndDevelopmentExpense",
        "경상연구개발비",
    ],
    "operating_income": [
        "us-gaap:OperatingIncomeLoss",
        "영업이익",
    ],
    "net_income": [
        "us-gaap:NetIncomeLoss",
        "ifrs-full:ProfitLoss",
        "ifrs-full_ProfitLoss",
        "당기순이익(손실)",
    ],
    # ── 현금흐름표(CF) ──
    "cash_from_operating": [
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "ifrs-full:CashFlowsFromUsedInOperatingActivities",
        "영업활동현금흐름",
    ],
    "cash_from_investing": [
        "us-gaap:NetCashProvidedByUsedInInvestingActivities",
        "ifrs-full:CashFlowsFromUsedInInvestingActivities",
        "투자활동현금흐름",
    ],
    "cash_from_financing": [
        "us-gaap:NetCashProvidedByUsedInFinancingActivities",
        "ifrs-full:CashFlowsFromUsedInFinancingActivities",
        "재무활동현금흐름",
    ],
    "capital_expenditure": [
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        "자본적지출",
    ],
}


# {원본이름: 정규화이름} 형태로 뒤집어서, 실제 조회에 쓰기 편하게 만듦
def build_reverse_concept_map() -> dict:
    """{원본이름: 정규화이름} 형태로 뒤집어서, 실제 조회에 쓰기 편하게 만듦"""
    reverse = {}
    for normalized, raw_list in CONCEPT_MAP.items():
        for raw in raw_list:
            if raw in reverse:
                # 이미 다른 정규화 이름에 등록된 raw concept이 또 나오면 즉시 알림
                raise ValueError(f"중복 매핑 발견: '{raw}'가 '{reverse[raw]}'와 '{normalized}' 둘 다에 등록됨")
            reverse[raw] = normalized
    return reverse


REVERSE_CONCEPT_MAP = build_reverse_concept_map()


# 원본 concept을 정규화된 이름으로 변환. 매핑 없으면 원본 그대로 반환
def get_normalize_concept(raw_concept: str) -> str:
    return REVERSE_CONCEPT_MAP.get(raw_concept, raw_concept)


if __name__ == "__main__":
    reverse = build_reverse_concept_map()
    print(f"매핑 성공: {len(reverse)}개")
