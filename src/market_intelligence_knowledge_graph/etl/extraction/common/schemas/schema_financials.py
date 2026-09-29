from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class FinancialSilverDoc(BaseModel):
    """Silver(financials 컬렉션)에 저장되는 재무 데이터 문서 하나의 스키마"""

    # Pydantic은 기본적으로 자신이 아는 타입(str, int 등)만 허용함
    # ObjectId(MongoDB 전용 타입)처럼 Pydantic이 원래 모르는 타입을 필드에 쓰려면 이 설정으로 "이런 임의의 타입도 허용해라"라고 알려줘야 함
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── 식별키 ──
    # "cik:0001045810" 또는 "dart:00126380". 어느 회사의 값인지 나타냄
    entity_id: str

    # 이 값이 EDGAR에서 왔는지 DART에서 왔는지. "edgar" | "dart"
    source: str

    # Bronze(edgar_financials 또는 dart_financials)의 원본 문서 _id
    # 이 값으로 "이 정규화된 수치가 어느 원본 문서에서 나왔는지" 역추적 가능
    # EDGAR: 원본 문서 1개 -> ObjectId 하나
    # DART: 계산에 쓰인 원본 문서 여러 개(Q1+H1+Q1_Q3+FY 중 실제 존재하는 것들) -> ObjectId 리스트
    source_ref: ObjectId | list[ObjectId]

    # ── 이름 ──
    # 정규화된 공통 이름(우리가 CONCEPT_MAP으로 만든 이름). 예: "revenue", "total_assets"
    # EDGAR/DART 무관하게 같은 재무 개념이면 항상 같은 문자열
    concept: str

    # 원본 그대로의 이름. EDGAR면 "us-gaap:Revenues", DART면 "ifrs-full_Revenue" 등
    # CONCEPT_MAP에 매핑이 안 된 경우, concept과 raw_concept이 같은 값이 됨(원본 그대로 통과)
    raw_concept: str

    # 영문 표시 이름 (EDGAR의 label 필드에서 그대로 가져옴)
    label_en: str | None = None

    # 한글 표시 이름 (CONCEPT_MAP 확장 시 채워 넣을 필드, 지금은 대부분 비어있음)
    label_ko: str | None = None

    # 실제 금액
    value: float | None

    # 통화 단위. "USD" | "KRW"
    currency: str | None = None

    # ── 분류/계층 ──
    # 어느 재무제표인지. "BS"(재무상태표) | "IS"(손익계산서) | "CF"(현금흐름표)
    # | "CIS"(포괄손익계산서, DART만) | "SCE"(자본변동표, DART만)
    statement_type: str | None = None

    # 연결재무제표 여부. DART는 fs_div 기준으로 true/false, EDGAR는 이 개념이 없어 None
    consolidated: bool | None = None

    # 재무제표 안에서의 계층 깊이(들여쓰기 단계). EDGAR만 채워짐(get_structured_statement 기반)
    # DART는 이 계층 API가 없어서 항상 None
    depth: int | None = None

    # 이 값이 "총계/소계" 줄인지 여부. 밸리AI 화면의 굵은 글씨 줄과 대응
    # EDGAR만 채워짐(depth와 같은 이유)
    is_total: bool | None = None

    # 이 값이 표준 재무제표 항목과 얼마나 정확히 매칭됐는지(0~1). EDGAR의 구조화 API에서만 나옴
    confidence: float | None = None

    # ── 기간 ──
    # 이 값이 커버하는 기간의 시작일. 재무상태표류(시점값)는 보통 None
    period_start: datetime | None = None

    # 이 값의 기준일(재무상태표) 또는 기간 종료일(손익계산서 등)
    period_end: datetime | None = None

    # 회계연도
    fiscal_year: int | None = None

    # "Q1" | "Q2" | "Q3" | "Q4" | "FY" — 분기인지 연간인지
    fiscal_period: str | None = None


class EdgarFinancialBronzeDoc(BaseModel):
    """Bronze(edgar_financials 컬렉션)에 저장되는 EDGAR 원본 문서 하나의 스키마"""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId | None = Field(default=None, alias="_id")
    # 삽입 전(API에서 막 받은 데이터): 아직 _id 없음 -> None
    # 조회 시(DB에서 읽어온 데이터): 이미 MongoDB가 발급한 값이 들어있음
    # 두 상황 모두에서 같은 DTO를 쓰기 위해 Optional로 둠

    # "cik:0001045810" 형식. get_financials()에서 추가한 필드(원본 API 응답엔 없음)
    entity_id: str

    # "NVDA" 등. get_financials()에서 추가한 필드(원본엔 없음)
    ticker: str

    # XBRL 표준 태그. 예: "us-gaap:Revenues", "ifrs-full:Revenue"
    # (us-gaap과 ifrs-full 둘 다 허용 — 미국기업은 us-gaap, 20-F 외국기업은 ifrs-full을 씀)
    concept: str

    # concept을 사람이 읽기 좋게 풀어쓴 영문 이름
    label: str

    # 실제 값. 두 필드가 사실상 같은 값을 담고 있음(edgartools가 원래 이렇게 중복 제공)
    value: float | None
    numeric_value: float | None

    # 단위. "USD"(금액) 또는 "shares"(주식 수) 등
    unit: str

    # "instant"(특정 시점, 재무상태표류) | "duration"(기간 동안, 손익계산서/현금흐름표류)
    period_type: str

    # 이 값이 해당하는 기간. instant면 period_start는 보통 None
    period_start: datetime | None
    period_end: datetime

    # 어느 회계연도, 어느 분기(Q1~Q4, FY)의 보고서에 실린 값인지
    # 주의: 같은 사실이 여러 fiscal_year에 "비교 재무제표"로 반복 등장할 수 있음(중복 아님)
    fiscal_year: int
    fiscal_period: str

    # 우리가 직접 추론해서 추가한 필드(원본엔 없음)
    # instant=BS, duration+"ProvidedBy"/"UsedIn"패턴=CF, 나머지 duration=IS로 판정
    statement_type: str


class DartFinancialBronzeDoc(BaseModel):
    """Bronze(dart_financials 컬렉션)에 저장되는 DART 원본 문서 하나의 스키마"""

    # arbitrary_types_allowed: ObjectId라는 낯선 타입을 필드로 허용
    # populate_by_name:        "_id"(MongoDB 원본 키)와 "id"(파이썬 필드명) 둘 다로 생성 가능하게 허용
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # MongoDB가 자동 부여하는 _id. alias="_id"로 원본 키 이름과 매칭
    # populate_by_name=True 덕분에 DartFinancialBronzeDoc(**raw_item)처럼 "_id" 키로 넘겨도 인식됨
    # (이걸 넣어야 나중에 "이 계산값이 어느 원본 문서들에서 나왔는지" 역추적 가능)
    # 삽입 전(API에서 막 받은 데이터): 아직 _id 없음 -> None
    # 조회 시(DB에서 읽어온 데이터): 이미 MongoDB가 발급한 값이 들어있음
    # 두 상황 모두에서 같은 DTO를 쓰기 위해 Optional로 둠
    id: ObjectId | None = Field(default=None, alias="_id")

    entity_id: str
    # "dart:00126380" 형식. get_financials()에서 추가한 필드(원본 API 응답엔 없음)

    rcept_no: str
    # 이 값이 실린 보고서의 접수번호(14자리)

    # 보고서 종류 코드. "11013"(1분기) | "11012"(반기) | "11014"(3분기) | "11011"(사업보고서)
    reprt_code: str

    # 사업연도. "2025" 등
    bsns_year: str

    # DART 내부 회사 식별자(8자리). entity_id의 원본이 되는 값
    corp_code: str

    # 재무제표 종류 코드/이름. "BS"/재무상태표, "IS"/손익계산서, "CF"/현금흐름표,
    # "CIS"/포괄손익계산서, "SCE"/자본변동표
    sj_div: str
    sj_nm: str

    # IFRS 표준 코드(있으면). 예: "ifrs-full_Revenue". 한국 고유 개념은 "dart_" 접두사가 붙기도 함
    account_id: str | None

    # 한글 계정과목명. 예: "매출액"
    account_nm: str

    # 계정의 세부 구성 요소 설명(파이프로 구분된 계층 힌트). 대부분 "-"(빈 값)로 채워짐
    account_detail: str | None

    # 연결(CFS) / 별도(OFS) 구분. 우리는 CFS만 가져옴
    """
    CFS(Consolidated Financial Statements) = 연결재무제표
        → 모회사 + 종속회사(자회사) 전부 합쳐서 하나의 회사인 것처럼 작성한 재무제표
    OFS(Individual/separate Financial Statements) = 별도재무제표
        → 모회사 단독 실적만, 자회사 지분은 "투자자산" 한 줄로만 반영
    """
    fs_div: str | None = None

    # 당기(현재 회계연도) 관련 정보. thstrm_amount는 콤마 포함된 문자열(숫자 변환 필요)
    thstrm_nm: str | None = None
    thstrm_dt: str | None = None
    thstrm_amount: str

    # 전기(1년 전) 값. 같은 문서 안에 동봉되지만 Silver에선 별도로 안 씀(별도 연도 호출로 대체)
    frmtrm_nm: str | None = None
    frmtrm_amount: str | None = None

    # 전전기(2년 전) 값. 위와 동일한 이유로 Silver에선 안 씀
    bfefrmtrm_nm: str | None = None
    bfefrmtrm_amount: str | None = None

    # 재무제표 안에서의 표시 순서. 계층은 아니지만 대략적인 그룹 추정에 참고 가능
    ord: str

    # 통화. "KRW"
    currency: str

    # 우리가 직접 추가한 필드(원본엔 없음). "Q1" | "H1" | "Q1_Q3" | "FY"
    # 어느 reprt_code에서 온 값인지 표시 — DART는 이게 "단독"이 아니라 "누적"임에 주의
    period_label: str
