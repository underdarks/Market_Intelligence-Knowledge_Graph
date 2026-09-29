from edgar import *
import re

set_identity("MIKG Research your.email@example.com")

c = Company("NVDA")
f = [x for x in c.get_filings(form="10-K") if x.form == "10-K"][0]
txt = f.text()

# 고객사 서술이 있는지
for kw in ["customer", "Customers", "one customer", "significant customer"]:
    print(kw, ":", txt.count(kw))


# 매출 집중도 서술 찾기 (보통 "accounted for X% of revenue" 형태)
for m in list(re.finditer(r"accounted for.{0,80}%.{0,60}revenue", txt, re.I))[:5]:
    s = max(0, m.start() - 200)
    print("\n---")
    print(txt[s : m.end() + 200])
