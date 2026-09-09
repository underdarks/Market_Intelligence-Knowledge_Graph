from edgar import Company, set_identity

from market_intelligence_knowledge_graph.adapters.base import CompanyAdapter
from market_intelligence_knowledge_graph.config import SEC_IDENTITY

set_identity(SEC_IDENTITY)


class EdgarCompanyAdapter(CompanyAdapter):
    def fetch(self, id: str) -> dict:
        c = Company(cik_or_ticker=id)
        return {"company": c, "id": id}

    def to_node(self, raw: dict) -> dict | None:

        c: Company = raw["company"]
        d = c.data

        # ETF-신탁 제외, entity_type으로 거르면 TSMC(값이 "other")가 누락되므로 SIC 유무로 판별
        if not d.sic:
            return None

        return {
            "entity_id": f"cik:{str(d.cik).zfill(10)}",  # PK. cik를 10자리로 0-padding 후 접두사 부여
            "cik": str(d.cik).zfill(10),  # API 재호출 시 그대로 쓸 원본 CIK
            "name": d.name,  # 현재 등록 사명
            "former_names": [
                f["name"] for f in (d.former_names or [])
            ],  # 과거 사명 목록. 옛 문서에 다른 이름으로 나와도 같은 회사로 매칭하기 위함
            "aliases": [],  # 지금은 빈 배열. 10-K 등에서 발견되는, 표기("TSMC" 등)를 이후 파이프라인에서 누적
            "tickers": list(d.tickers or []),  # 배열. 한 회사가 복수 티커 보유 가능(예: BRK-B/A)
            "exchanges": list(c.get_exchanges() or []),  # tickers와 같은 순서로 대응
            "industry_code": d.sic or None,  # SIC 코드. 빈 문자열이면 None으로 정규화
            "industry_scheme": "sic",  # 이 코드가 SIC 체계임을 명시, (한국 KSIC과 섞이면 비교 불가하므로 필수)
            "entity_type": d.entity_type,  # operating/other 등. 필터링엔 쓰지 말 것(TSMC처럼 other인데 유효한 사업회사가 있음)
            "fiscal_year_end": d.fiscal_year_end,  # MMDD. 회사마다 결산월이 달라 시계열 비교 시 필요
            "state_of_incorporation": d.state_of_incorporation or None,  # 법인 설립 주. 외국 법인은 자주 빈 값
            "ein": (
                d.ein if d.ein and d.ein != "000000000" else None
            ),  # 국세청 고유번호. ETF 등엔 더미값 "000000000"이 들어있어 걸러냄
            "public_float": c.public_float,  # 유통 시가총액. 별도 시세 API 없이 시총 필터용
            "shares_outstanding": c.shares_outstanding,  # 발행주식수
            "jurisdiction": "US",  # 국가 구분. DART 등 다른 소스 추가 시 필터 기준
            "source_system": "edgar",  # 이 노드가 어느 어댑터에서 왔는지 (edgar/dart/manual)
        }
