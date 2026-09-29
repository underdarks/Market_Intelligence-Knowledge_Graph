# LLM이 문단을 보고 판정한 위탁 관계 결과
from typing import Literal
from pydantic import BaseModel, Field


# 문서(10-K, 20-F 등)에서 grep으로 찾은 문단 하나(공용 반환 타입)
class ParagraphMention(BaseModel):
    from_ticker: str  # 예: "AVGO" — 이 문단이 들어있는 10-K 문서의 주체 회사 티커
    from_cik: str  # 예: "0001730168" — 위 회사의 SEC CIK, 10자리로 0-padding됨
    accession: str  # 예: "0001730168-25-000121" — 이 문단이 실린 10-K 문서의 SEC 고유번호
    form: str  # 예: "10-K", "20-F" — 문서 종류. "10-K/A"(수정본)가 아니라 원본인지 확인하는 용도
    file_date: str  # 예: "2025-12-18" — 이 문서가 SEC에 제출된 날짜
    matched_alias: str  # 예: "TSMC" — grep이 어떤 표기로 이 문단을 찾았는지(같은 문단이 "TSMC"와 "Taiwan Semiconductor" 두 표기 모두에 걸려 중복으로 잡힐 수 있음)
    text: str  # 예: "...approximately 95% of ... TSMC...", grep이 찾아낸 실제 원문 발췌. LLM 판정(judge_paragraph)에 그대로 넘어감


# LLM이 문단을 읽고 나온 직후의 "가공되지 않은 순수 응답 DTO"
class SupplyJudgement(BaseModel):
    """
    SupplyJudgment는 LLM에게 "이 형식으로만 답해"라고 강제하는 클래스(DTO)
        1. LLM 출력 형식을 코드로 정의
        2. 검증 자동화
        3. 변환 자동화
    """

    # 이 필드에 들어올 수 있는 값은 딱 3가지
    #
    #   "disclosed" → 수치까지 명시된 경우
    #     예: "approximately 95% of the wafers manufactured by our CMs were produced by TSMC"
    #     (AVGO 10-K 실제 문장. "95%"라는 구체적 숫자가 있어서 disclosed)
    #
    #   "stated" → 관계는 있는데 숫자가 없는 경우
    #     예: "We utilize foundries, such as TSMC, and Samsung Electronics"
    #     (NVDA 10-K 실제 문장. "TSMC를 쓴다"는 사실은 있지만 몇 %인지는 안 나옴)
    #
    #   "none" → 애초에 위탁 관계를 말하는 문단이 아닌 경우
    #     예: "TSMC also fabricates wafers for other companies, including some of our competitors"
    #     (이건 우리 회사와 TSMC의 관계가 아니라 "TSMC가 경쟁사에도 판다"는 얘기.
    #      TSMC라는 단어는 있지만 관계 서술이 아니라서 none)
    #
    # judge_paragraph()에서 이 값이 "none"이면 그래프에 아무것도 안 만들고 그냥 버림

    confidence: Literal["disclosed", "stated", "none"] = Field(
        description="disclosed: 의존 비중 수치 명시됨. stated: 관계 서술만 있고 수치 없음. "
        "none: 실제 위탁 관계 서술이 아님"
    )  # LLM이 자유 텍스트로 답하면 오탈자·표현 차이가 생기니 Literal로 값 종류를 3개로 강제

    # 예: "95%"라고 써있으면 0.95로 변환해서 저장. 저장 형식이 0~1 사이 소수인 이유는
    # 나중에 "70% 이상 기업 필터링" 같은 쿼리를 짤 때 dependency_pct > 0.7 로 바로 비교 가능하게 하려고
    # confidence가 "stated"나 "none"이면 이 값은 항상 None (수치 자체가 없으니까)
    dependency_pct: float | None = Field(
        default=None, description="0~1 사이 비율. 수치가 없으면 null"
    )  # 공시에 수치가 없는 문단이 대부분이라 optional

    # 어떤 종류의 위탁인지 자유 텍스트로 씀. 예:
    #   "wafer_fabrication" → 웨이퍼(반도체 원판) 생산을 맡기는 것
    #   "assembly_test"     → 완성된 칩을 조립하고 테스트하는 것을 맡기는 것
    #   "packaging"         → 칩을 포장(패키징)하는 것을 맡기는 것
    # 아직 정해진 목록(enum)이 아니라 LLM이 문맥 보고 자유롭게 적음.
    # 나중에 실제로 어떤 값들이 나오는지 데이터를 보고 확정된 목록으로 좁힐 수 있음
    process_type: str | None = Field(default=None, description="wafer_fabrication / assembly_test / packaging 등")

    # 예: "The paragraph explicitly states 95% of wafers are produced by TSMC, a specific quantified figure."
    # 이건 그래프에 안 들어가고(또는 Evidence에 참고용으로만 들어가고), 사람이 나중에 "LLM이 왜 이렇게 판정했지?"를 확인하고 싶을 때 보는 디버깅/검증용 텍스트
    reasoning: str = Field(
        description="판정 근거를 한두 문장으로"
    )  # 필수 필드. LLM이 왜 이렇게 판정했는지 남겨야 나중에 사람이 사후 검증할 수 있음


class EvidenceData(BaseModel):
    """Evidence 노드로 적재될 필드"""

    accession: str  # SEC 문서 고유번호. 이 값으로 원문 URL 재구성 가능
    form: str  # "10-K" 또는 "10-K/A" 등. 원본/수정본 구분용 (AMD 파이프라인 버그 재발 방지)
    file_date: str  # 공시 제출일. relation.as_of_date와 같은 값을 재사용하게 됨
    matched_alias: str  # grep에서 어떤 표기(ex. "TSMC"/"Taiwan Semiconductor")로 찾았는지 기록
    quoted_text: str  # LLM이 판정 근거로 삼은 원문 문단 그대로. 사람이 육안 검증할 때 필요
    extraction_method: str = "llm"  # 자동 추출인지 수동 큐레이션인지 구분. 수동은 "manual"로 명시
    reasoning: str  # SupplyJudgment.reasoning을 그대로 옮겨옴. 근거 채택 이유를 함께 보관


# SupplyRelation 노드로 적재될 필드
class RelationData(BaseModel):

    # 여기 도달했다는 건 이미 관계가 있다고 확정된 상태라는 뜻(타입으로 그 보장을 표현)
    # disclosed: 공시에 의존 비중이 수치로 명시된 경우
    # stated : 관계는 서술돼 있지만 수치는 없는 경우
    confidence: Literal["disclosed", "stated"]

    # confidence가 "disclosed"일 때만 값이 채워짐. 0~1 사이 소수로 저장
    #   예: "95%" → 0.95 로 변환해서 저장 (그래야 나중에 dependency_pct > 0.7 같은
    #       쿼리로 "70% 이상 의존 기업"을 바로 필터링할 수 있음)
    # confidence가 "stated"면 이 값은 항상 None (애초에 수치 자체가 공시에 없으니까)
    dependency_pct: float | None = None

    # 어떤 종류의 위탁인지. 아직 고정된 값 목록(enum)이 아니라 LLM이 문맥 보고 자유롭게 채움
    #   예: "wafer_fabrication" → 웨이퍼(반도체 원판) 생산을 맡기는 것
    #       "assembly_test"     → 완성된 칩을 조립하고 테스트하는 것을 맡기는 것
    #       "packaging"         → 칩을 포장(패키징)하는 것을 맡기는 것
    # 이 값은 relation_id를 만들 때도 쓰임: 같은 두 회사(예: AVGO→TSMC) 사이에
    # 웨이퍼 위탁과 조립 위탁이 동시에 존재할 수 있어서, process_type이 달라야
    # 서로 다른 SupplyRelation 노드로 구분됨
    process_type: str

    # 이 관계를 확인한 공시의 제출일(YYYY-MM-DD 형식 문자열)
    #   예: "2025-12-18" (AVGO 10-K 제출일)
    # paragraph.file_date를 그대로 옮겨서 씀. 스키마 문서의 "시간 모델" 결정에 따라 지금은 이 관계에 대해 "가장 최근에 확인한 시점" 하나만 유지함
    as_of_date: str


# judge_paragraph()의 최종 반환 타입. Company 매칭 + Evidence + Relation 묶음
class JudgedRelation(BaseModel):
    from_ticker: str  # 아직 entity_id(cik:...) 형식 아님. 원본 티커 그대로
    to_ticker: str  # entity_id 변환은 load_relations.py의 책임으로 남겨둠(책임 분리)
    from_entity_id: str  # 그래프 MATCH에 실제로 쓰이는 값. "cik:0001730168" 형식
    to_entity_id: str  # 그래프 MATCH에 실제로 쓰이는 값
    evidence: EvidenceData
    relation: RelationData


# LLM이 Business 섹션에서 뽑아낸 제품/사업 정보
class ProductInfo(BaseModel):
    # 제품 또는 사업 라인 이름. 예: "AI GPU", "Gaming GPU", "자동차용 SoC"
    name: str

    # 제품 카테고리(대분류). 예: "semiconductor", "software"
    # 나중에 Product 노드의 category 필드로 그대로 들어감(스키마 문서 1-2 참고)
    category: str

    # 이 회사가 이 제품에 대해 하는 역할
    #   "designs" → 설계만 함 (예: ARM이 CPU 설계도만 만드는 경우)
    #   "sells"   → 판매만 함 (예: OEM이 남의 설계를 자기 브랜드로 파는 경우)
    #   "both"    → 설계도 하고 판매도 함 (대부분의 팹리스가 여기 해당)
    role: Literal["designs", "sells", "both"]

    # 이 판단의 근거가 된 원문 문장. Evidence 노드의 quoted_text로 그대로 들어감
    quoted_text: str

    # 근거(LLM이 판단)
    confidence: Literal["disclosed", "stated"]

    # 이 관계를 확인한 공시의 제출일(YYYY-MM-DD 형식 문자열)
    as_of_date: str


class ProductJudgement(BaseModel):
    products: list[ProductInfo]


# 회사가 특정 공정/기술을 수행한다는 판정 결과
class ProcessCapability(BaseModel):
    process_name: str  # 예: "CoWoS" — 사람이 읽는 공정/기술 이름. Process 노드의 name 속성으로 들어감

    # 예: "advanced_packaging" — Process 노드의 process_id 조합에 쓰이는 정규화된 값
    # ("process:" + process_type 형태로, 기존 derive_process.py의 wafer_fabrication/assembly_test와 같은 명명 규칙을 따름)
    process_type: str

    # SupplyRelation/RelationData와 동일한 2단계 체계 재사용
    #   "disclosed" → 수치나 구체적 사실이 명시된 경우
    #   "stated"    → 사실은 서술되나 구체적 수치·범위 없이 일반적으로 언급된 경우
    # 예: TSMC 20-F의 "we offer... CoWoS advanced packaging services"는 구체적 수치는 없지만 자사 서비스로 명확히 서술 → stated
    confidence: Literal["disclosed", "stated"]
    
    # 이 근거가 어느 문서 종류에서 왔는지(ex. 20-F)
    # (derive_process.py가 만드는 PERFORMS는 "supply_relation"을 씀 — 필드명 통일)
    derived_from: str

    # 이 판단의 근거가 된 원문 문장 그대로. Evidence 역할을 하는 필드
    # (SupplyRelation처럼 별도 Evidence 노드를 만들지 않고, DESIGNS/SELLS처럼 이 필드 자체를 엣지 속성으로 직접 저장하는 방식을 따름)
    quoted_text: str
    accession: str  # 이 문장이 실린 문서의 SEC 고유번호(출처 추적용 ex."0001628280-26-025362")
    form: str  # 예: "20-F" — 문서 종류. 10-K/20-F 등 어떤 폼에서 나온 근거인지 구분
    file_date: str  # 예: "2026-04-16" — 문서 제출일. RelationData.as_of_date와 같은 역할


# LLM이 문단을 보고 판정한 공정 수행 여부 원시 결과
class ProcessJudgement(BaseModel):
    # "disclosed" → 구체적 수치나 세부사항과 함께 서술 (예: "CoWoS 생산량 X% 증설")
    # "stated"    → 수행한다는 사실만 서술, 구체적 수치 없음
    #   예: TSMC 20-F "We also offer... CoWoS advanced packaging services"
    # "none"      → 유효한 근거 아님 (상표권 목록, 목차, 단순 언급 등)
    #   예: "CoWoS, TSMC-SoIC, ... are some of our registered trademarks"
    confidence: Literal["disclosed", "stated", "none"]

    # 판정 근거를 한두 문장으로. 디버깅/사후검증용
    reasoning: str
