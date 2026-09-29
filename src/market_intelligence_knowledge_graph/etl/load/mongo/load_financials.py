from collections import Counter
from locale import normalize

from enums.statement_type import get_statement_type
from market_intelligence_knowledge_graph.config.mongo_db import get_mongodb
from market_intelligence_knowledge_graph.etl.extraction.common.schemas.schema_financials import (
    DartFinancialBronzeDoc,
    EdgarFinancialBronzeDoc,
    FinancialSilverDoc,
)
from market_intelligence_knowledge_graph.etl.extraction.concept_map import get_normalize_concept
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_hierarchy_financials import (
    get_hierarchy_template,
)


# edgar_financials(Bronze)를 읽어서 정규화 + 계층정보 결합 → financials(Silver)에 적재
def load_financials_from_edgar(chunk_size: int = 1000):
    db = get_mongodb()
    edgar_financials_collection = db["edgar_financials"]
    financials_collection = db["financials"]

    last_id = None
    processed_count = 0
    unmapped_concepts = Counter()

    # edgar_financials에서 raw 데이터 추출
    while True:
        query = {"_id": {"$gt": last_id}} if last_id else {}
        cursor = edgar_financials_collection.find(query).sort(key_or_list="_id", direction=1).limit(limit=chunk_size)
        chunk = list(cursor)
        financials_docs = []

        if not chunk:  # 가져올 데이터가 없다면
            break

        last_id = chunk[-1]["_id"]

        # concept_map 전처리
        for raw_item in chunk:
            item = EdgarFinancialBronzeDoc(**raw_item)
            raw_concept = item.concept  # ex. "concept": "us-gaap:CashAndCashEquivalentsAtCarryingValue"
            concept = get_normalize_concept(raw_concept)

            if concept == raw_concept:
                unmapped_concepts[raw_concept] += 1

            # 이 레코드의 statement_type("BS" 등)에 맞는 계층 템플릿을 가져옴(BS면 BalanceSheet 템플릿, IS면 IncomeStatement 템플릿 각각 캐싱된 걸 재사용)
            statement_type = item.statement_type  # ex. BS
            statement_name = get_statement_type(statement_type)

            hierarchy_info = {}
            if statement_name:
                template = get_hierarchy_template(ticker=item.ticker, statement_type=statement_name)
                concept_short = raw_concept.split(":")[-1]
                hierarchy_info = template.get(concept_short, {})

            doc = FinancialSilverDoc(
                entity_id=item.entity_id,
                source="edgar",
                source_ref=raw_item["_id"],  # _id는 DTO에 안 넣었으니 raw_item에서 그대로
                concept=concept,
                raw_concept=raw_concept,
                label_en=item.label,
                value=item.numeric_value if item.numeric_value is not None else item.value,
                currency=item.unit,
                statement_type=statement_type,
                consolidated=None,
                depth=hierarchy_info.get("depth"),
                is_total=hierarchy_info.get("is_total"),
                period_start=item.period_start,
                period_end=item.period_end,
                fiscal_year=item.fiscal_year,
                fiscal_period=item.fiscal_period,
            )
            financials_docs.append(doc.model_dump())

        # financials로 적재
        financials_collection.insert_many(documents=financials_docs)

        processed_count += len(chunk)
        print(f"현재까지 {processed_count}개 데이터 처리 완료...")

    print("edgar Raw -> Silver 데이터 적재 완료!")
    print(f"매핑 안 된 concept 수: {len(unmapped_concepts)}개")
    # for concept, count in unmapped_concepts.most_common():  # 인자 없으면 전체
    #     print(f"  {concept}: {count}회")


def parse_dart_amount(raw: str | None) -> float | None:
    """DART API 금액 문자열을 float로 변환
    예: "1,234,567" -> 1234567.0 / "-" 또는 빈값 -> None (공시 안 된 값)
    """
    if raw is None or raw.strip() in ("", "-"):
        return None
    try:
        return float(raw.replace(",", ""))  # 콤마 제거 후 변환
    except ValueError:
        return None  # 예상 못 한 포맷(주석/특수문자 섞인 경우 등) 방어


def compute_quarterly_value(group: dict[str, DartFinancialBronzeDoc | None]) -> dict[str, float | None]:
    """누적값(Q1/H1/Q1_Q3/FY)에서 분기 단독값을 역산

    DART는 재무제표를 항상 "연초부터 누적"으로 보고함 (EDGAR와 가장 다른 지점)
    예: "H1"(반기보고서)의 thstrm_amount는 "4~6월 매출"이 아니라 "1~6월 누적 매출"
    → 그래서 2분기 "단독" 매출을 얻으려면 H1(1~6월 누적) - Q1(1~3월 누적) 계산이 필요함

    입력값 group은 그룹핑 단계에서 이미 "같은 계정·같은 연도"끼리 모아둔 딕셔너리:
    {"Q1": Bronze문서|None, "H1": Bronze문서|None, "Q1_Q3": Bronze문서|None, "FY": Bronze문서|None}
    (4개 보고서 중 아직 공시 안 됐거나 데이터가 없는 건 키 자체가 없을 수 있음)
    """
    q1 = parse_dart_amount(group["Q1"].thstrm_amount) if group.get("Q1") else None
    h1 = parse_dart_amount(group["H1"].thstrm_amount) if group.get("H1") else None
    q1_q3 = parse_dart_amount(group["Q1_Q3"].thstrm_amount) if group.get("Q1_Q3") else None
    fy = parse_dart_amount(group["FY"].thstrm_amount) if group.get("FY") else None
    # 참고: 여기서 읽는 건 오직 thstrm_amount(당기 누적값)뿐.
    # Bronze 원본엔 frmtrm_amount(전기), bfefrmtrm_amount(전전기)도 같이 들어있지만
    # 우리는 "그 연도 값이 필요하면 그 연도로 API를 따로 호출해서 thstrm_amount로 받는다"는
    # 방침이라, 한 문서 안에 딸려오는 전기/전전기 필드는 의도적으로 쓰지 않음

    return {
        # Q1은 애초에 "1분기 단독" 보고서라 누적분이 없음 -> 역산 없이 그대로 사용
        "Q1": q1,
        # Q2 단독값 = H1(1~6월 누적) - Q1(1~3월 누적)
        # h1, q1 둘 다 값이 있어야 계산 가능. 하나라도 None이면(보고서 미공시 등)
        # "틀린 값을 억지로 만들지 말고 모른다고 표시하자"는 원칙에 따라 None 반환
        "Q2": (h1 - q1) if (h1 is not None and q1 is not None) else None,
        # Q3 단독값 = Q1_Q3(1~9월 누적) - H1(1~6월 누적)
        "Q3": (q1_q3 - h1) if (q1_q3 is not None and h1 is not None) else None,
        # Q4 단독값 = FY(연간 총계) - Q1_Q3(1~9월 누적)
        # DART는 4분기만 따로 보고하는 리포트가 없어서(사업보고서=FY가 마지막), 역산이 유일한 방법
        "Q4": (fy - q1_q3) if (fy is not None and q1_q3 is not None) else None,
        # FY는 "연간 총계" 그 자체가 필요한 값이라, 애초에 역산 대상이 아니라 원본 그대로 사용
        "FY": fy,
    }


def _group_key(item: DartFinancialBronzeDoc) -> tuple:
    """분기 단독값 계산을 위한 그룹 키
    같은 계정을 Q1/H1/Q1_Q3/FY 4개 보고서에서 각각 찾아 한데 모아야 하므로,"재무제표 종류(BS/IS/CF)+계정+연결여부+사업연도"가 같으면 같은 그룹으로 묶음
    (period_label은 그룹 키에서 일부러 뺐음 — 이걸 넣으면 Q1/H1/Q1_Q3/FY가 서로 다른 그룹이 되어버려서 애초에 "모아서 계산"하려는 목적 자체가 깨짐)
    """
    account_key = item.account_id or item.account_nm  # IFRS 표준 코드 우선, 없으면 한글 계정명으로 폴백
    return (item.sj_div, account_key, item.fs_div, item.bsns_year)


def load_financials_from_dart(chunk_size: int = 1000):
    db = get_mongodb()
    dart_financials_collection = db["dart_financials"]
    financials_collection = db["financials"]

    # 회사 단위로 순회하는 이유: DART 데이터는 누적값이라 그룹핑이 필수인데,컬렉션 전체를 한 번에 메모리에 올리면 부담되니 회사 단위로 끊어서 처리
    # SELECT DISTINCT corp_code FROM dart_financials_collection;
    corp_codes = dart_financials_collection.distinct("corp_code")
    unmapped_concepts = Counter()  # CONCEPT_MAP에 없는 계정 추적 (나중에 매핑 확장할 때 참고 자료)
    processed_count = 0

    for corp_code in corp_codes:
        # 데이터가 1만개이고, batch_size(1000)이면 1000개씩 * 10. 즉, 10번의 network i/o발생
        cursor = dart_financials_collection.find({"corp_code": corp_code}).batch_size(chunk_size)

        # 그룹핑 결과를 담을 딕셔너리: 그룹키 -> {period_label: 검증된 문서}
        # 예: ("BS", "ifrs-full_Assets", "CFS", "2025") -> {"Q1": doc, "H1": doc, "Q1_Q3": doc, "FY": doc}
        groups: dict[tuple, dict[str, DartFinancialBronzeDoc]] = {}

        for raw_item in cursor:
            item = DartFinancialBronzeDoc(**raw_item)  # Bronze 원본 필드 누락/타입 오류를 여기서 바로 검증
            key = _group_key(item)
            groups.setdefault(key, {})[item.period_label] = item

        silver_docs = []

        for (sj_div, account_key, fs_div, bsns_year), group in groups.items():
            quarterly = compute_quarterly_value(group)  # Q1~Q4, FY 단독값 계산

            raw_concept = account_key
            concept = get_normalize_concept(raw_concept)  # DART/EDGAR 공통 CONCEPT_MAP으로 정규화 시도
            if concept == raw_concept:
                unmapped_concepts[raw_concept] += 1

            # 이 그룹의 계산에 실제로 쓰인 원본 문서들의 _id 목록
            # (Q1/H1/Q1_Q3/FY 중 존재하는 것만 모음 — 전부 다 있으리라는 보장 없음)
            source_refs = [doc.id for doc in group.values()]

            # 그룹 내 문서는 계정/연결여부/연도가 전부 같으므로, 대표값(entity_id 등)은 아무 문서에서나 꺼내도 됨
            any_doc = next(iter(group.values()))
            consolidated = fs_div == "CFS"  # 연결(CFS)이면 True, 별도(OFS)면 False

            for fiscal_period, value in quarterly.items():
                if value is None:
                    continue  # 계산/원본 값이 없는 분기는 저장하지 않음 (빈 문서로 채우지 않음)

                doc = FinancialSilverDoc(
                    entity_id=any_doc.entity_id,
                    source="dart",
                    source_ref=source_refs,  # TODO: 아래 참고 — 타입 위반, 확정 안 됨
                    concept=concept,
                    raw_concept=raw_concept,
                    label_en=None,  # DART는 영문 라벨 없음
                    label_ko=any_doc.account_nm,
                    value=value,
                    currency=any_doc.currency,
                    statement_type=sj_div,
                    consolidated=consolidated,
                    depth=None,  # DART는 계층 API 없어서 항상 None (EDGAR만 채워짐)
                    is_total=None,
                    period_start=None,
                    period_end=None,
                    fiscal_year=int(bsns_year),
                    fiscal_period=fiscal_period,
                )
                silver_docs.append(doc.model_dump())

        if silver_docs:
            financials_collection.insert_many(silver_docs)

        processed_count += len(silver_docs)
        print(f"{corp_code} 처리 완료 (누적 {processed_count}건)")

    print("dart Raw -> Silver 데이터 적재 완료!")
    print(f"매핑 안 된 concept 수: {len(unmapped_concepts)}개")
    # for concept, count in unmapped_concepts.most_common():  # 인자 없으면 전체
    #     print(f"  {concept}: {count}회")
