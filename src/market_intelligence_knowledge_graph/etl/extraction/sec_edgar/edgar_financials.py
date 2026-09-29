from datetime import datetime
from collections import Counter
from edgar import Company, set_identity
from market_intelligence_knowledge_graph.config.config import SEC_IDENTITY
from market_intelligence_knowledge_graph.utils.utils import to_entity_id, date_to_datetime

set_identity(SEC_IDENTITY)


# 한 행(row)의 period_type과 concept을 보고 BS/IS/CF/UNKNOWN을 판정
def _infer_statement_type(row) -> str:
    """
    period_type이 "instant"(특정 시점의 스냅샷)이면 재무상태표(BS)로 판정
    예: us-gaap:Assets(총자산), us-gaap:Liabilities(총부채) → 전부 instant였음(실측 확인)
    "그 시점에 얼마가 있었나"를 나타내는 값이라 BS(재무상태표)가 맞음
    """
    if row["period_type"] == "instant":
        return "BS"  # 재무상태표

    """
      period_type이 "duration"(일정 기간 동안 발생한 것)이면 IS 또는 CF 둘 중 하나
      이 시점에선 아직 확정 못 함 — concept 이름을 더 봐야 구분 가능
      (instant가 아니라는 것만 알았지, IS인지 CF인지는 모르는 상태)
    """
    if row["period_type"] == "duration":
        concept = row["concept"]
        """
          concept 이름 안에 "ProvidedBy"나 "UsedIn"이라는 문자열이 포함돼 있으면 CF로 판정
          ex) us-gaap:NetCashProvidedByUsedInOperatingActivities(영업활동현금흐름)이 태그 이름 자체에 "ProvidedBy"와 "UsedIn"이 다 들어있어서 걸림(실측 확인)
          현금흐름표 항목들은 보통 "~로부터 제공된/~에 사용된 현금"이라는 서술 방식이라 이 패턴이 CF를 가려내는 단서가 됨
        """
        if "ProvidedBy" in concept or "UsedIn" in concept:
            return "CF"  # 현금흐름표

        """
          "ProvidedBy"도 "UsedIn"도 없는 나머지 duration은 손익계산서(IS)로 판정(기본값 취급)
          예: us-gaap:Revenues(매출), us-gaap:NetIncomeLoss(순이익) → 둘 다 이 패턴에 해당(실측 확인)
        """
        return "IS"

    return "UNKNOWN"  # period_type이 "instant"도 "duration"도 아닌 경우(이론상 거의 없어야 하지만 방어 차원) 또는 예상 못 한 값이 들어왔을 때 나중에 이 값이 실제로 나오면 원인을 봐야


# SEC_EDGAR기반 회사의 XBRL 재무 데이터를 가져와서 us-gaap만 필터링, 최근 N년만, statement_type 추론까지
def get_edgar_financials(ticker: str, years_back: int = 5) -> list[dict]:
    c = Company(ticker)
    df = c.get_facts().to_dataframe()

    # 1. us-gaap 태그만 남기기
    # df["concept"]는 전체 행의 concept 컬럼값들 (Series라는 1차원 배열 같은 것)
    # .str.startswith("us-gaap:")는 각 값이 "us-gaap:"로 시작하는지 True/False로 검사
    # df[조건]은 "조건이 True인 행만 남긴다는 뜻"(필터링)
    df = df[df["concept"].str.startswith(("us-gaap:", "ifrs-full:"))]

    # 2. 최근 N년만 남기기
    current_year = datetime.now().year
    df = df[df["fiscal_year"] >= current_year - years_back]

    # 3. 각 행마다 statement_type을 새로 계산해서 컬럼으로 추가
    # axis=1은 "행 단위로 함수를 적용해라"는 뜻 (기본값 axis=0은 열 단위)
    df["statement_type"] = df.apply(_infer_statement_type, axis=1)

    # 4. DataFrame을 dict 리스트로 변환
    # to_dict("records")는 [{"key": ..., "value": ...}, {"key": ..., "value":...}] 형태로 만들어줌
    records = df.to_dict("records")

    # 5. 각 record에 entity 식별 정보 추가(나중에 MongoDB에서 어느 회사 것인지 알아야 하닌깐)
    for r in records:
        r["ticker"] = ticker
        r["entity_id"] = to_entity_id(id=ticker, country="us")
        r["period_start"] = date_to_datetime(r.get("period_start"))
        r["period_end"] = date_to_datetime(r.get("period_end"))

    return records


if __name__ == "__main__":
    records = get_edgar_financials("NVDA")

    # 밸리AI에 나온 세부 항목들과 대응될 만한 concept 찾기
    keywords = [
        "Receivable",
        "Inventory",
        "Prepaid",
        "Goodwill",
        "Intangible",
        "SellingGeneral",
        "ResearchAndDevelopment",
        "InterestIncome",
    ]

    for kw in keywords:
        matches = [r for r in records if kw in r["concept"]]
        print(f"{kw}: {len(matches)}건")
        if matches:
            print("  예:", matches[0]["concept"])

    print("====" * 20)

    records = get_edgar_financials("NVDA")
    print(len(records))
    print(records[0])
    print(set(r["statement_type"] for r in records))  # BS/IS/CF/UNKNOWN이 어떻게 나오는지
    print(Counter(r["statement_type"] for r in records))

    """
      key_concepts = [
          "us-gaap:Revenues",  # 매출 (IS 항목일 것으로 예상)
          "us-gaap:CostOfRevenue",  # 매출원가 (IS)
          "us-gaap:NetIncomeLoss",  # 순이익 (IS)
          "us-gaap:Assets",  # 총자산 (BS 항목일 것으로 예상)
          "us-gaap:Liabilities",  # 총부채 (BS)
          "us-gaap:StockholdersEquity",  # 자본 (BS)
          "us-gaap:CashAndCashEquivalentsAtCarryingValue",  # 현금 (BS)
          "us-gaap:NetCashProvidedByUsedInOperatingActivities",  # 영업활동현금흐름 (CF일 것으로 예상)
          "us-gaap:NetCashProvidedByUsedInInvestingActivities",  # 투자활동현금흐름 (CF일 것으로 예상)
          "us-gaap:NetCashProvidedByUsedInFinancingActivities",  # 재무활동현금흐름 (CF일 것으로 예상)  
      ]
    """

    cf_concepts = set(r["concept"] for r in records if r["statement_type"] == "CF")
    for c in sorted(cf_concepts)[:20]:
        print(c)
