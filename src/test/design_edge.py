import re
from edgar import Company, Filing, set_identity
from market_intelligence_knowledge_graph.config import SEC_IDENTITY
from market_intelligence_knowledge_graph.extraction.sec_edgar.sec_edgar_text_extraction import get_business_section, get_original_10K

set_identity(SEC_IDENTITY)

c = Company("NVDA")
f = [x for x in c.get_filings(form="10-K") if x.form == "10-K"][0]
txt = f.text()

# Item 1 (사업 개요) 섹션 찾기 - 텍스트에서 헤더 문자열로 위치 찾기
# 첫 번째 "Item 1." (목차)를 건너뛰고, 두 번째부터 찾기
first_idx = txt.find("Item 1.")
idx = txt.find("Item 1.", first_idx + 1)  # first_idx 다음부터 다시 검색

idx_end = txt.find("Item 1A.", idx + 1)
item1_text = txt[idx:idx_end]  # Item 1A- Item 1 하면 Item1의 총 텍스트 길이가 나옴
print(len(item1_text))  # Item1. 섹션 길이(40664)
# print(item1_text[:3000])


c = Company("AVGO")
f = [x for x in c.get_filings(form="10-K") if x.form == "10-K"][0]
txt = f.text()


# 회사들 Item1 섹션 첫번제 부터 나오는지 아닌지 확인
for ticker in ["NVDA", "AVGO", "AMD", "QCOM"]:
    filling: Filing | None = get_original_10K(ticker)  # sec 공시 내용
    section = get_business_section(filling)
    print(f"{ticker}: {len(section)}자")
    print(section[:150].replace("\n", " "))
    print()
