import requests
from market_intelligence_knowledge_graph.adapters.base import CompanyAdapter
from market_intelligence_knowledge_graph.config import DART_API_KEY
from market_intelligence_knowledge_graph.utils.entity import to_entity_id


# api docs: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002
class DartCompanyAdapter(CompanyAdapter):
    """DART 기업개황 데이터를 공통 Company 스키마로 변환"""

    def fetch(self, id: str) -> dict:
        res: requests.Response = requests.get(
            url="https://opendart.fss.or.kr/api/company.json", params={"crtfc_key": DART_API_KEY, "corp_code": id}
        )
        data = res.json()

        # DART는 HTTP 200이어도 Body status로 성공/실패 별도 확인해야함
        if data.get("status") != "000":  # 000은 정상
            raise RuntimeError(f"DART API 오류: {data.get('status')} {data.get('message')}")
        return data

    def to_node(self, raw: dict) -> dict | None:
        # acc_mt("12")를 EDGAR의 fiscal_year_end 형식(MMDD)에 맞춰 정규화 일자는 말일로 가정 — 정확한 정규화 규칙은 추후 재검토 필요
        acc_mt = raw.get("acc_mt")
        fiscal_year_end = f"{acc_mt}31" if acc_mt else None

        # 대표이사가 콤마로 여러 명 연결될 수 있음
        ceo_names = [n.strip() for n in raw.get("ceo_nm", "").split(",") if n.strip()]

        to_entity_id()
        return {
            "entity_id": to_entity_id(
                id=raw["corp_code"], country="kr"
            ),  # PK. corp_code에 "dart:" 접두사. 예: "dart:00126380"
            "corp_code": raw["corp_code"],  # 예: "00126380" — DART 내부 식별자 원본값. EDGAR의 cik 필드와 대응
            "name": raw.get("corp_name"),  # 예: "삼성전자(주)" — 법인격("주") 포함 정식명
            "former_names": [],  # DART엔 사명 변경 이력 API가 없어서 항상 빈 배열 (EDGAR former_names와 형식만 맞춤)
            "aliases": (
                [raw.get("corp_name_eng")] if raw.get("corp_name_eng") else []
            ),  # 예: ["SAMSUNG ELECTRONICS CO,.LTD"] — 영문명. EDGAR 10-K 원문 표기와 거의 일치해서 SAME_AS 매칭에 바로 쓸 수 있는 값
            "tickers": (
                [raw["stock_code"]] if raw.get("stock_code", "").strip() else []
            ),  # 예: ["005930"] — 종목코드. 공백이면 비상장이라 빈 배열 처리(corp_code와 다른 값이므로 여기서 혼동하지 않도록 분리해서 저장)
            "exchanges": [],  # DART 응답엔 거래소 구분 필드가 없음(corp_cls로 유가/코스닥 구분은 되지만 exchanges 형식으로 안 맞아서 일단 비워둠 — 필요하면 corp_cls를 매핑해서 채울 것)
            "industry_code": raw.get("induty_code")
            or None,  # ex. "264" - KSIC 코드. 3자리로 보임(EDGAR SIC는 4자리, 자릿수 다름)
            "industry_scheme": "ksic",  # 이 코드가 KSIC 체계임을 명시. SIC와 섞이면 비교 불가하므로 필수 필드
            "entity_type": "operating",  # DART엔 EDGAR의 entity_type 같은 구분 필드가 없어서 일단 고정값(비상장 소형법인까지 걸러야 하면 나중에 조건 추가 필요)
            "fiscal_year_end": fiscal_year_end,  # 예: "1231" — acc_mt("12")에 "31"을 붙여 EDGAR의 MMDD 형식에 맞춤. 실제 결산일이 항상 말일인지는 미검증, 일단 가정으로 처리
            "state_of_incorporation": None,  # DART엔 대응 개념 없음(설립일 est_dt는 있지만 "설립 지역"과는 다른 정보)
            "ein": raw.get("bizr_no")
            or None,  # 예: "1248100998" — 사업자등록번호. EDGAR의 ein과 성격은 비슷하나 체계는 다름
            "public_float": None,  # DART 기업개황엔 시가총액 관련 필드 없음. 재무정보 API에서 별도 확보 필요(미착수)
            "shares_outstanding": None,  # 위와 동일한 이유로 미확보
            "jurisdiction": "KR",  # 국가 구분. 미국 기업과 섞인 그래프에서 필터링 기준이 되는 핵심 필드
            "source_system": "dart",  # 이 노드가 어느 어댑터에서 왔는지 표시. EDGAR는 "edgar"
            "ceo_names": ceo_names,  # EDGAR엔 없는 필드 ex. ["전영현", "노태문"] — 원본 ceo_nm이 콤마로 여러 명 연결돼 있어 분리한 리스트
        }
