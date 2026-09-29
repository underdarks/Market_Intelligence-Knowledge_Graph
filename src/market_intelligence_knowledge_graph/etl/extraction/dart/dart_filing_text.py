"""
mikg/extraction/filing_text_dart.py

DART 사업보고서 본문(business/risk_factors/management_discussion)을
FilingTextBronzeDoc으로 추출하는 모듈.
"""

import zipfile
from pathlib import Path

import requests
from lxml import etree

from market_intelligence_knowledge_graph.config.config import DART_API_KEY
from market_intelligence_knowledge_graph.config.mongo_db import get_mongodb
from market_intelligence_knowledge_graph.etl.extraction.common.schemas.schema_filling_text import FilingTextBronzeDoc

# "찾을 섹션 3개(business/risk_factors/mda)의 제목 텍스트를 어떤 한글 키워드로 검색할지" 정의한 매핑
SECTION_TITLE_KEYWORDS: dict[str, list[str]] = {
    "business": ["사업의 내용"],
    "risk_factors": ["위험관리 및 파생거래", "우발부채 등에 관한"],
    "management_discussion": ["이사의 경영진단 및 분석의견"],
}


def _parse_note(note: str) -> tuple[str, str, str] | None:
    """AASSOCNOTE 문자열을 (prefix, romanIdx, subIdx)로 분해.
    형식이 안 맞는 특수 항목(COVER, TTL_CEO_CERT 등)은 None 반환.
    """
    parts = note.split("-")
    if len(parts) < 4:
        return None
    return parts[0], parts[2], parts[3]  # prefix, romanIdx, subIdx


def extract_section_dynamic(root, title_keyword: str) -> tuple[str, str, str]:
    """제목 텍스트로 섹션을 찾고, AASSOCNOTE 규칙으로 끝 경계를 동적으로 판단해 본문을 추출.
    회사마다 ATOCID/AASSOCNOTE 번호가 다르므로 고정 상수 대신 매번 탐색함.
    """
    all_titles = list(root.iter("TITLE"))

    # 1. 시작 지점 찾기
    start_idx = None
    for i, el in enumerate(all_titles):
        text = (el.text or "").strip()
        if title_keyword in text:
            start_idx = i
            break

    if start_idx is None:
        return "", "", ""  # 이 회사 문서엔 해당 섹션 자체가 없음

    start_el = all_titles[start_idx]
    title_ko = (start_el.text or "").strip()
    title_en = start_el.get("ENG", "")
    start_note = _parse_note(start_el.get("AASSOCNOTE", ""))

    # 2. 끝 경계 찾기
    end_idx = len(all_titles)  # 못 찾으면 문서 끝까지
    if start_note:
        _, start_roman, start_sub = start_note
        for i in range(start_idx + 1, len(all_titles)):
            note = _parse_note(all_titles[i].get("AASSOCNOTE", ""))
            if not note:
                continue
            _, roman, sub = note

            if start_sub == "0":
                # 대분류 자체 -> romanIdx가 바뀌는 지점이 끝
                if roman != start_roman:
                    end_idx = i
                    break
            else:
                # 특정 하위항목 -> 바로 다음 TITLE이 끝 (첫 루프에서 바로 걸림)
                end_idx = i
                break

    # 3. start_idx~end_idx 사이의 모든 형제 요소(문단/표) 수집
    #    (기존 extract_section_by_atocid의 텍스트 수집 로직 재사용 —
    #     TITLE의 다음 형제(sibling)들을 document order로 순회하며 TABLE은 마크다운 변환)
    start_el_in_tree = start_el
    end_el_in_tree = all_titles[end_idx] if end_idx < len(all_titles) else None

    collecting = False
    collected: list[str] = []
    for el in root.iter():
        if el is start_el_in_tree:
            collecting = True
            continue
        if end_el_in_tree is not None and el is end_el_in_tree:
            break
        if not collecting:
            continue

        if el.tag == "TABLE":
            md = table_to_markdown(el)
            if md:
                collected.append(md)
        elif el.tag not in ("TABLE-GROUP", "TBODY", "TR", "TD", "TU", "COLGROUP", "COL", "TITLE"):
            text = (el.text or "").strip()
            if text:
                collected.append(text)

    return title_ko, title_en, "\n".join(collected)


def parse_xml_lenient(xml_path: str):
    """DART XML이 종종 표준 문법을 어겨서(이스케이프 안 된 & 등)
    표준 xml.etree로는 파싱이 실패함. lxml의 recover=True로
    깨진 부분은 건너뛰고 나머지를 최대한 복구해서 파싱.
    """
    parser = etree.XMLParser(recover=True, encoding="utf-8")
    tree = etree.parse(xml_path, parser)
    return tree.getroot()


def table_to_markdown(table_el) -> str:
    """DART XML의 TABLE(TR 안에 TD/TU 셀) 구조를 간단한 마크다운 표로 변환.
    TU는 TD와 거의 동일하되 "단위가 있는 셀"(날짜, 금액 등)을 의미하는 DART 자체 태그.
    """
    rows = []
    for tr in table_el.iter("TR"):
        cells = []
        for cell in tr:
            if cell.tag in ("TD", "TU"):
                cells.append((cell.text or "").strip())
        if any(cells):  # 완전히 빈 행(레이아웃 구분용)은 제외
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def download_and_extract_document(rcept_no: str, extract_dir: str = "./download_files") -> str:
    """document.xml API 호출 → zip 저장 → 압축 해제 → 메인 xml 파일 경로 반환.
    zip 안에 rcept_no.xml(본문) 외에 첨부파일(감사보고서 등)이 같이 들어있을 수 있어서 파일명이 rcept_no와 정확히 일치하는 것만 골라야 함.
    """
    url = "https://opendart.fss.or.kr/api/document.xml"
    params = {"crtfc_key": DART_API_KEY, "rcept_no": rcept_no}
    resp = requests.get(url, params=params)
    resp.raise_for_status()

    zip_path = Path(extract_dir) / f"{rcept_no}.zip"
    zip_path.write_bytes(resp.content)

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        z.extractall(extract_dir)

    main_filename = f"{rcept_no}.xml"
    if main_filename not in names:
        raise FileNotFoundError(f"{rcept_no}: 메인 문서({main_filename})를 zip에서 못 찾음. 실제 파일 목록: {names}")

    return str(Path(extract_dir) / main_filename)


# 가장 최근 사업보고서(A001)의 rcept_no를 조회
def find_annual_report_rcept_no(corp_code: str) -> str:
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "pblntf_detail_ty": "A001",  # 사업보고서 (대문자 필수)
        "bgn_de": "20240101",
        "end_de": "20260911",
        "page_count": 10,
    }
    resp = requests.get(url, params=params).json()

    if resp.get("status") != "000":
        raise RuntimeError(f"조회 실패: {resp.get('status')} {resp.get('message')}")

    reports = resp["list"]
    return reports[0]["rcept_no"]  # 최신 1건


# DART 사업보고서 하나를 다운로드+파싱해서 3개 섹션의 FilingTextBronzeDoc 리스트로 변환.risk_factors는 2개 구간이라 최대 4건이 나올 수 있음.
def parse_dart_document(
    rcept_no: str,
    entity_id: str,
    doc_type: str,
    fiscal_year: int,
    filed_date: str,
) -> list[FilingTextBronzeDoc]:
    xml_path = download_and_extract_document(rcept_no)
    root = parse_xml_lenient(xml_path)

    docs: list[FilingTextBronzeDoc] = []

    for section_id, keywords in SECTION_TITLE_KEYWORDS.items():
        for keyword in keywords:
            title_ko, title_en, text = extract_section_dynamic(root, keyword)

            if not text:
                print(f"[SKIP] {rcept_no}: '{keyword}' 못 찾음 (section_id={section_id})")
                continue

            docs.append(
                FilingTextBronzeDoc(
                    entity_id=entity_id,
                    source="dart",
                    doc_type=doc_type,
                    rcept_no=rcept_no,
                    section_id=section_id,
                    section_title=title_ko,
                    section_title_en=title_en,
                    text=text,
                    fiscal_year=fiscal_year,
                    filed_date=filed_date,
                )
            )

    return docs
