from edgar import *
import time

set_identity("MIKG Research your.email@example.com")  # 본인 이메일로 교체

TARGETS = ["AVGO", "AMD", "NVDA", "QCOM", "MRVL"]

# TSMC는 문서마다 표기가 달라서 여러 패턴으로 찾아야 함
# 정식명 / 약칭 / 대만 언급 등
KEYWORDS = ["Taiwan Semiconductor", "TSMC"]


for ticker in TARGETS:
    print("=" * 70)
    c = Company(ticker)

    # ★ 수정본(10-K/A) 제외하고 원본만 필터링
    """
      문제는 get_filings(form="10-K")가 10-K뿐 아니라 10-K/A(수정본)도 같이 잡는다는 것
      edgartools가 form="10-K"를 "10-K 계열 전부"로 해석해서, 아래에 필터링 걸어버림
    """
    originals = [f for f in c.get_filings(form="10-K") if f.form == "10-K"]
    if not originals:
        print(f"[{ticker}] 원본 10-K 없음")
        continue

    f = originals[0]
    txt = f.text()
    print(f"[{ticker}] {f.form} | {f.accession_no} | {f.filing_date} | 길이 {len(txt):,}")

    for kw in KEYWORDS:
        r = f.grep(kw)
        print(f"  '{kw}': {len(r)}건")

    time.sleep(0.5)
