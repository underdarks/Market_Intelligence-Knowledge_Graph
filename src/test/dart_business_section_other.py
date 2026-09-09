import requests
import zipfile
import io
import re

KEY = "3804b422a767ab11da3156147a89fbcd2f5374bd"


# ── 1단계: 전체 법인 목록(CORPCODE.xml) 받기 ──
def fetch_corp_code_xml() -> str:
    r = requests.get(
        "https://opendart.fss.or.kr/api/corpCode.xml",
        params={"crtfc_key": KEY},
    )
    zfile = zipfile.ZipFile(io.BytesIO(r.content))
    return zfile.read("CORPCODE.xml").decode("utf-8")


# ── 2단계: 종목코드로 corp_code 찾기 ──
def find_corp_code(xml_content: str, stock_code: str) -> str | None:
    marker = f"<stock_code>{stock_code}</stock_code>"
    idx = xml_content.find(marker)
    if idx == -1:
        return None
    block = xml_content[max(0, idx - 250) : idx + len(marker)]
    match = re.search(r"<corp_code>(\d+)</corp_code>", block)
    return match.group(1) if match else None


# ── 3단계: 최신 사업보고서 접수번호 조회 ──
def get_latest_rcept_no(corp_code: str) -> str | None:
    r = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={"crtfc_key": KEY, "corp_code": corp_code, "pblntf_detail_ty": "A001", "bgn_de": "20250101"},
    )
    data = r.json()
    if data["status"] != "000":
        print(f"  [ERR] {data['status']} {data['message']}")
        return None

    # "기재정정" 등 수정 신고서를 제외하고 원본만 고름
    originals = [item for item in data["list"] if "기재정정" not in item["report_nm"]]
    if not originals:
        return None
    return originals[0]["rcept_no"]


# ── 4단계: 사업보고서 원문 다운로드 ──
def get_document_text(rcept_no: str) -> str | None:
    r = requests.get(
        "https://opendart.fss.or.kr/api/document.xml",
        params={"crtfc_key": KEY, "rcept_no": rcept_no},
    )
    try:
        zfile = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        print(f"  [ERR] ZIP 아님: {r.content[:200]}")
        return None
    main_file = f"{rcept_no}.xml"
    if main_file not in zfile.namelist():
        print(f"  [WARN] 파일명 다름: {zfile.namelist()}")
        return None
    return zfile.read(main_file).decode("utf-8")


# ── 5단계: "2. 주요 제품 및 서비스" 섹션 위치 + AASSOCNOTE 값 확인 ──
def find_product_sections(xml_content: str) -> list[tuple[int, str, str]]:
    """AASSOCNOTE 코드로 '주요 제품 및 서비스' 섹션을 전부 찾음 (부문별로 여러 개 나올 수 있음)"""
    pattern = r'<TITLE[^>]*AASSOCNOTE="(L-0-2-2-L\d)"[^>]*>([^<]*)</TITLE>'
    return [(m.start(), m.group(1), m.group(2)) for m in re.finditer(pattern, xml_content)]


# ── 실행 ──
if __name__ == "__main__":
    OTHER_INDUSTRY = [
        {"name": "현대자동차", "stock_code": "005380"},
        {"name": "KB금융", "stock_code": "105560"},
        {"name": "이마트", "stock_code": "139480"},
    ]

    print("전체 법인 목록 받는 중...")
    corp_xml = fetch_corp_code_xml()
    print(f"완료 ({len(corp_xml)}자)\n")

    print("=== corp_code 확인 ===")
    for t in OTHER_INDUSTRY:
        t["corp_code"] = find_corp_code(corp_xml, t["stock_code"])
        print(f"{t['name']}: corp_code={t['corp_code']}")
    print()

    print("=== 섹션 검증 ===")
    for t in OTHER_INDUSTRY:
        if not t.get("corp_code"):
            print(f"--- {t['name']} : corp_code 없음, 스킵 ---\n")
            continue

        print(f"--- {t['name']} ---")
        rcept_no = get_latest_rcept_no(t["corp_code"])
        if rcept_no is None:
            continue
        print(f"  rcept_no: {rcept_no}")

        doc = get_document_text(rcept_no)
        if doc is None:
            continue
        print(f"  문서 길이: {len(doc)}자")

        sections = find_product_sections(doc)  # 이제 리스트가 옴
        if sections:
            print(f"  ✅ {len(sections)}개 섹션 발견")
            for idx, assocnote, title in sections:
                print(f"    [{assocnote}] {title} (위치={idx})")
                print("    ", doc[idx : idx + 250].replace("\n", " "))
        else:
            print("  ❌ 못 찾음")


print("KB 금융 테스트")
r = requests.get(
    "https://opendart.fss.or.kr/api/list.json",
    params={"crtfc_key": KEY, "corp_code": "00688996", "pblntf_detail_ty": "A001", "bgn_de": "20250101"},
)
data = r.json()
print(data["status"], data["message"])
for item in data["list"]:
    print(item["report_nm"], "|", item["rcept_no"], "|", item["rcept_dt"], "|", item.get("rm"))
