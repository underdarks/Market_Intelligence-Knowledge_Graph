import xml.etree.ElementTree as ET
import requests
import re
import zipfile
from lxml import etree

url = "https://opendart.fss.or.kr/api/document.xml"
params = {
    "crtfc_key": "3804b422a767ab11da3156147a89fbcd2f5374bd",
    "rcept_no": "20260515002842",  # 지난번 봤던 삼성전기 사업보고서 접수번호
}
resp = requests.get(url, params=params)

# print(f"status_code: {resp.status_code}")
# print(f"Content-Type: {resp.headers.get('Content-Type')}")
# print(f"응답 크기: {len(resp.content)} bytes")

with open("20260515002842.xml", "r", encoding="utf-8") as f:
    content = f.read()

# 목차 TD 안의 로마숫자/번호 붙은 챕터명만 추출
# toc_items = re.findall(r"<TD[^>]*>([IVX]+\.\s*[^<]+|\s+\d+\.\s*[^<]+)</TD>", content)
# for item in toc_items:
#     print(item.strip())


"""
사업보고서(연간) TITLE/ATOCID 구조가 분기보고서와 같은지 검증하는 스크립트.
1. 삼성전기(00126371)의 최신 사업보고서(reprt_code=11011) rcept_no 찾기
2. document.xml 다운로드 + 압축 해제
3. TITLE 구조를 지난번 확인한 분기보고서 ATOCID(9,10/53,54/39,40/17,24)와 비교
"""


CORP_CODE = "00126371"
API_KEY = "3804b422a767ab11da3156147a89fbcd2f5374bd"


def parse_xml_lenient(xml_path: str):
    """DART XML이 종종 표준 문법을 어겨서(이스케이프 안 된 & 등)
    표준 xml.etree로는 파싱이 실패함. lxml의 recover=True로
    깨진 부분은 건너뛰고 나머지를 최대한 복구해서 파싱.
    """
    parser = etree.XMLParser(recover=True, encoding="utf-8")
    tree = etree.parse(xml_path, parser)
    return tree.getroot()


# 1. 사업보고서 rcept_no 찾기 (공시검색 API)
def find_annual_report_rcept_no(corp_code: str) -> str:
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "pblntf_detail_ty": "A001",  # 소문자 -> 대문자로 수정 (사업보고서)
        "bgn_de": "20240101",  # 검색 시작일 명시 (기본값이 좁을 수 있어 넉넉히 잡음)
        "end_de": "20260911",  # 오늘 날짜
        "page_count": 10,
    }
    resp = requests.get(url, params=params).json()

    if resp.get("status") != "000":
        raise RuntimeError(f"조회 실패: {resp.get('status')} {resp.get('message')}")

    reports = resp["list"]
    print(f"사업보고서 {len(reports)}건 발견")
    for r in reports:
        print(f"  {r['rcept_no']} - {r['report_nm']} ({r['rcept_dt']})")

    return reports[0]["rcept_no"]  # 최신 1건


# 2. document.xml 다운로드 + 압축 해제
def download_and_extract(rcept_no: str) -> str:
    url = "https://opendart.fss.or.kr/api/document.xml"
    params = {"crtfc_key": API_KEY, "rcept_no": rcept_no}
    resp = requests.get(url, params=params)

    zip_path = f"{rcept_no}.zip"
    with open(zip_path, "wb") as f:
        f.write(resp.content)

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        z.extractall()

    print(f"압축 해제된 파일: {names}")
    return names[0]  # xml 파일명 반환


# 3. TITLE/ATOCID 구조 비교
def compare_title_structure(xml_path: str):
    known_atocids = {
        9: "II. 사업의 내용 (시작)",
        10: "III. 재무에 관한 사항 (business 끝 경계)",
        53: "II.5 위험관리 및 파생거래 (시작)",
        54: "II.6 주요계약 및 연구개발활동 (risk_factors_A 끝 경계)",
        39: "XI.2 우발부채 등에 관한사항 (시작)",
        40: "XI.3 제재 등과 관련된 사항 (risk_factors_B 끝 경계)",
        17: "IV. 이사의 경영진단 및 분석의견 (시작)",
        24: "V. 회계감사인의 감사의견 등 (mda 끝 경계)",
    }

    root = parse_xml_lenient(xml_path)  # ET.parse(xml_path) 대신 이걸로 교체

    found = {}
    for el in root.iter("TITLE"):
        atocid = el.get("ATOCID")
        if atocid and int(atocid) in known_atocids:
            found[int(atocid)] = (el.text or "").strip()

    print("\n=== ATOCID 매칭 결과 (분기보고서 기준값과 비교) ===")
    for atocid, expected_desc in known_atocids.items():
        actual_text = found.get(atocid, "❌ 못 찾음")
        print(f"  ATOCID={atocid} 기대={expected_desc}")
        print(f"           실제 텍스트: {actual_text}")

    missing = set(known_atocids) - set(found)
    if missing:
        print(f"\n⚠️ 사업보고서에서 못 찾은 ATOCID: {missing}")
        print("→ 분기보고서와 챕터 구조가 다르다는 뜻. 매핑 재확인 필요")
    else:
        print("\n✅ 8개 ATOCID 전부 일치. 파싱 함수 그대로 사업보고서에도 적용 가능")


if __name__ == "__main__":
    rcept_no = find_annual_report_rcept_no(CORP_CODE)
    xml_filename = download_and_extract(rcept_no)
    compare_title_structure(xml_filename)
