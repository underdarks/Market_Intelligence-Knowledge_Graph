import re
import zipfile
import io
import requests

from market_intelligence_knowledge_graph.config import DART_API_KEY

# 제조/서비스업 관점 "주요 제품 및 서비스" 섹션의 AASSOCNOTE 코드
# (금융업 관점 L2는 반도체 스코프 밖이라 다루지 않음)
_PRODUCT_SECTION_CODE = "L-0-2-2-L1"


# EDGAR: accession_no = "0001730168-25-000121"  (AVGO 10-K 하나를 가리키는 고유번호), {CIK}-{연도2자리}-{순번}
# DART:  rcept_no      = "20260310002820"        (삼성전자 사업보고서 하나를 가리키는 고유번호) {YYYYMMDD}{순번}
def get_business_report_rcept_no(corp_code: str) -> tuple[str, str]:
    """최신 원본 사업보고서(기재정정 제외)의 접수번호를 반환"""
    r = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "pblntf_detail_ty": "A001",  # 공시상세유형 코드. "A001" = 사업보고서만 골라서 조회
            "bgn_de": "20250101",  # 검색 시작일(Begin Date) "2025년 1월 1일 이후"에 제출된 공시만 조회
        },
    )
    data = r.json()

    # DART는 HTTP 200이어도 바디의 status로 성공/실패를 따로 확인해야 함
    if data.get("status") != "000":
        print(f"  [ERR] list.json: {data.get('status')} {data.get('message')}")
        return None

    # 기재정정(수정신고)은 사업보고서 전체를 담고 있지 않을 수 있어 제외
    originals = [item for item in data["list"] if "기재정정" not in item["report_nm"]]
    if not originals:
        return None

    return (originals[0]["rcept_no"], originals[0]["rcept_dt"])


def get_document_text(rcept_no: str) -> str | None:
    """사업보고서 원본 ZIP을 받아서 메인 문서 텍스트를 반환"""
    r = requests.get(
        "https://opendart.fss.or.kr/api/document.xml",
        params={"crtfc_key": DART_API_KEY, "rcept_no": rcept_no},
    )
    try:
        zfile = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        print(f"  [ERR] ZIP 아님. 응답: {r.content[:200]}")
        return None

    main_file = f"{rcept_no}.xml"
    if main_file not in zfile.namelist():
        print(f"  [WARN] 예상 파일명 없음: {zfile.namelist()}")
        return None

    return zfile.read(main_file).decode("utf-8")


def get_product_section(xml_content: str) -> str | None:
    """AASSOCNOTE='L-0-2-2-L1'(제조/서비스업 주요 제품) 섹션 텍스트만 잘라서 반환

    끝점은 임시로 '다음 섹션 제목이 시작되는 지점'을 텍스트로 추정한다.
    (AASSOCNOTE 코드 체계의 다음 값이 정확히 뭔지 아직 확인 전 — 확인되면 교체 예정)
    """
    start_pattern = rf'<TITLE[^>]*AASSOCNOTE="{re.escape(_PRODUCT_SECTION_CODE)}"[^>]*>'
    start_match = re.search(start_pattern, xml_content)
    if start_match is None:
        return None

    start = start_match.start()

    # 임시: 같은 대분류(L-0-2-*) 안에서 다음 SECTION-2가 열리는 지점을 끝점으로 사용
    # (정확한 코드값 확인 전까지의 잠정 처리 — TODO: AASSOCNOTE 순서 확인 후 교체)
    next_match = re.search(r"<SECTION-2[^>]*>", xml_content[start_match.end() :])
    end = start_match.end() + next_match.start() if next_match else len(xml_content)

    return xml_content[start:end]
