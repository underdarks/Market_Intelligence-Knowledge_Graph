import requests
import zipfile
import io
import re

KEY = "3804b422a767ab11da3156147a89fbcd2f5374bd"

TARGETS = [
    {"corp_code": "00126380", "name": "삼성전자"},
    {"corp_code": "00164779", "name": "SK하이닉스"},
    {"corp_code": "00160843", "name": "DB하이텍"},
    {"corp_code": "00161383", "name": "한미반도체"},
    {"corp_code": "00126371", "name": "삼성전기"},
]


def get_latest_rcept_no(corp_code: str) -> str | None:
    r = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={"crtfc_key": KEY, "corp_code": corp_code, "pblntf_detail_ty": "A001", "bgn_de": "20250101"},
    )
    data = r.json()
    if data["status"] != "000":
        print(f"  [ERR] {data['status']} {data['message']}")
        return None
    return data["list"][0]["rcept_no"]


def get_document_text(rcept_no: str) -> str | None:
    r = requests.get(
        "https://opendart.fss.or.kr/api/document.xml",
        params={"crtfc_key": KEY, "rcept_no": rcept_no},
    )
    zfile = zipfile.ZipFile(io.BytesIO(r.content))
    main_file = f"{rcept_no}.xml"
    if main_file not in zfile.namelist():
        print(f"  [WARN] 파일명 다름: {zfile.namelist()}")
        return None
    return zfile.read(main_file).decode("utf-8")


def find_product_sections(xml_content: str) -> list[tuple[int, str, str]]:
    """AASSOCNOTE 코드로 '주요 제품 및 서비스' 섹션을 전부 찾음 (부문별로 여러 개 나올 수 있음)"""
    pattern = r'<TITLE[^>]*AASSOCNOTE="(L-0-2-2-L\d)"[^>]*>([^<]*)</TITLE>'
    return [(m.start(), m.group(1), m.group(2)) for m in re.finditer(pattern, xml_content)]


for t in TARGETS:
    print(f"=== {t['name']} ===")
    rcept_no = get_latest_rcept_no(t["corp_code"])
    if rcept_no is None:
        continue

    xml_content = get_document_text(rcept_no)
    if xml_content is None:
        continue

    idx = find_product_sections(xml_content)
    print(f"  본문 섹션 위치: {idx}")
    if idx is not None:
        print("  ", xml_content[idx : idx + 300].replace("\n", " "))
    else:
        print("  → 본문에서 못 찾음, 다음 섹션 제목이나 다른 표기 확인 필요")
    print()
