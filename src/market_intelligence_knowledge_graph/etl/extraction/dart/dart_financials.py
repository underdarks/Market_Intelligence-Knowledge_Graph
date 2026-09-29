from collections import Counter
import re
import time
import requests

from market_intelligence_knowledge_graph.config.config import DART_API_KEY, DART_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.etl.extraction.dart.dart_document import get_business_report_info
from market_intelligence_knowledge_graph.utils.utils import to_entity_id

"""
DART 보고서 코드 → 기간 라벨
 - 한국 관행상 반기/3분기는 "단독"이 아니라 "누적"임에 주의(edgar는 분기마다 데이터를 주는데 dart는 누적으로 줌)
    Q1(11013): 1분기만 (1~3월)
    H1(11012): 1분기+2분기 (1~6월 누적)
    Q1_Q3(11014): 1분기+2분기+3분기 (1~9월 누적)
    FY(11011): 1분기+2분기+3분기+4분기 (1~12월 전체)
"""

_REPRT_CODES = {
    "11013": "Q1",  # 1분기 단독
    "11012": "H1",  # 상반기 누적(1~2분기)
    "11014": "Q1_Q3",  # 1~3분기 누적
    "11011": "FY",  # 연간 전체
}


# 사업보고서 형태에서 사업연도만 뽑음
def _extract_bsns_year(report_nm: str) -> str | None:
    match = re.search(r"\((\d{4})\.", report_nm)
    return match.group(1) if match else None


# 지정한 reprt_code 하나에 대한 전체 재무제표를 조회
def _fetch_one_report(corp_code: str, bsns_year: str, reprt_code: str) -> list[dict]:
    r = requests.get(
        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
        params={
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": "CFS",
        },
    )
    data = r.json()

    if data.get("status") == "013":
        # 013 = 데이터 없음. 그 분기 보고서가 아직 없거나 공시 안 됐을 수 있어 정상 케이스로 처리
        print(f"  [SKIP] corp_code={corp_code} reprt_code={reprt_code}: 데이터 없음")
        return []

    if data.get("status") != "000":
        print(f"  [ERR] corp_code={corp_code} reprt_code={reprt_code}: {data.get('status')} {data.get('message')}")
        return []

    return data.get("list", [])


# DART 전체 재무제표를 4개 reprt_code(Q1/H1/Q1_Q3/FY) 전부 순회해서 원본 그대로 반환(bsns_year: 사업연도)
def get_dart_financials(corp_code: str, bsns_year: str) -> list[dict]:
    entity_id = to_entity_id(corp_code, country="kr")
    all_records = []  # 4개 보고서(Q1/H1/Q1_Q3/FY)에서 나온 값들

    for reprt_code, period_label in _REPRT_CODES.items():
        # 이번 순회의 reprt_code로 실제 API 호출. 그 보고서 하나의 전체 재무제표 항목들을 받음(예: reprt_code="11013"이면 1분기보고서의 BS/IS/CF 항목 전부)
        records = _fetch_one_report(corp_code, bsns_year, reprt_code)

        for rec in records:
            rec["entity_id"] = entity_id
            rec["period_label"] = (
                period_label  # 이 항목이 "어느 시점 보고서에서 왔는지" 표시 (Q1/H1/Q1_Q3/FY 중 하나), 나중에 Silver에서 Q2=H1-Q1 같은 계산을 할 때, 이 라벨로 어떤 보고서 값인지 구분함
            )
            # API 응답엔 fs_div가 없음(요청 파라미터일 뿐, 응답 필드로 echo 안 됨) 우리가 항상 CFS로만 요청하므로, 여기서 직접 채워넣어야 Bronze/Silver에서 값을 신뢰할 수 있음
            rec["fs_div"] = "CFS"  # CFS(Consolidated Financial Statements) = 연결재무제표

        all_records.extend(records)
        time.sleep(DART_RATE_LIMIT_SLEEP)

    return all_records


if __name__ == "__main__":
    records = get_dart_financials("00126380", "2023")  # 삼성전자 corp_code
    print(f"총 {len(records)}개")
    print(Counter(r["period_label"] for r in records))
