from edgar import Company, Filing
from market_intelligence_knowledge_graph.extraction.schemas import ParagraphMention

"""
    EDGAR 문서에서 텍스트 추출 메서드 모음
"""


def get_original_10K(ticker: str) -> Filing | None:
    c = Company(cik_or_ticker=ticker)
    originals = [f for f in c.get_filings(form="10-K") if f.form == "10-K"]
    return originals[0] if originals else None  # originals에 값이 있으면 originals[0] 리턴, 없으면 None 리턴


def get_original_20F(ticker: str) -> Filing | None:
    """원본 20-F(외국 발행인 연차보고서) Filing 객체를 반환. 없으면 None"""
    c = Company(ticker)
    filings = [f for f in c.get_filings(form="20-F")]
    return filings[0] if filings else None


# 원본 10-K(수정본 제외)에서 특정 회사의 여러 표기(aliases)를 언급한 문단을 뽑아 반환
def get_company_mentions(from_ticker: str, to_company_aliases: list[str]) -> list[ParagraphMention]:
    """
    미국 증권거래위원회(SEC)에 제출된 특정 기업의 최신 10-K(연례보고서) 원본 파일에서 타사 명칭(별칭)이 언급된 문단을 검색하여 추출하는 함수
     - from_ticker: 문서 주체 (예: "AVGO")
     - to_company_aliases: 찾으려는 대상 회사의 표기들 (예: ["Taiwan Semiconductor", "TSMC"])
    """

    f: Filing | None = get_original_10K(ticker=from_ticker)
    if f is None:
        return []
    results = []

    # 찾고자 하는 기업의 별칭(예: ["TSMC", "Taiwan Semiconductor"])을 하나씩 순회
    for alias in to_company_aliases:
        for hit in f.grep(pattern=alias):  # 핵심: 10-K 문서 전체에서 해당 별칭(alias)이 포함된 문단/구절을 검색
            results.append(
                ParagraphMention(
                    from_ticker=from_ticker,
                    from_cik=str(f.cik).zfill(10),  # CIK 번호를 10자리(앞에 0을 채움)로 표준화
                    accession=f.accession_no,  # 공시 고유 접수번호 (Accession Number)
                    form=f.form,  # 공시 서식 종류 ("10-K")
                    file_date=str(f.filing_date),  # 공시 제출 일자
                    matched_alias=alias,  # 매칭된 기업 별칭 키워드
                    text=str(hit),  # 매칭된 실제 본문 문단 텍스트
                )
            )

    return results


# 원본 10-K(수정본 제외)에서 Item 1(Business) 섹션 전체 반환하는 함수
def get_business_section(original_10K) -> str:
    if original_10K is None:
        return ""

    # XBRL 활용
    # .obj()가 이 문서를 그냥 HTML/텍스트로 보는 게 아니라,문서 안에 심어진 XBRL 태그(및 SEC 표준 문서 구조 정보)를 읽어서
    # 이 문서가 10-K 형식이구나"를 인식하고, 그에 맞는 전용 파서(TenK 클래스)로 변환해줌.
    # 이게 사람이 "Item 1." 이라는 글자를 눈으로 찾는 대신, 문서에 미리 붙어있는 구조 정보(인덱스 탭)를 그대로 읽어오는 방식
    tenk = original_10K.obj()

    # TenK 객체가 이미 XBRL 구조 정보를 바탕으로 섹션을 다 나눠놓은 상태라,.business 속성 하나만 접근하면 Item 1(Business) 섹션 텍스트가 바로 나옴.
    # 회사마다 "Item 1.", "ITEM 1.BUSINESS", "PART I ITEM 1." 등 표기가 달라도 전부 동일하게 동작함 (표기 방식이 아니라 구조 태그 기준으로 나누기 때문)
    # `or ""` 는 방어 코드: 아주 드물게 business 섹션 자체가 없거나 파싱이 실패해서 None이 반환되는 경우, 빈 문자열로 통일해서 호출하는 쪽에서 "None 체크"와 "빈 문자열 체크"를 둘 다 안 해도 되게 함
    return tenk.business or ""


def get_filing_mentions(filing: Filing, keyword: str) -> list[ParagraphMention]:
    """
    이미 확보된 Filing 객체(10-K든 20-F든 무관)에서 키워드를 언급한 문단을 grep으로 추출
     - filing: get_original_10k() 또는 get_original_20f() 등이 반환한 Filing 객체
     - keyword: 찾을 표현. 예: "CoWoS", "TSMC"
    """
    if filing is None:
        return []

    results = []
    for hit in filing.grep(keyword):
        results.append(
            ParagraphMention(
                from_ticker=filing.company,
                from_cik=str(filing.cik).zfill(10),
                accession=filing.accession_no,
                form=filing.form,
                file_date=str(filing.filing_date),
                matched_alias=keyword,
                text=str(hit),
            )
        )
    return results
