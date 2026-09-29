import json

from edgar import Company, get_company_tickers, set_identity

set_identity("PortfolioResearch rkdrl45617@gmail.com")

# 1. 기업정보
datas = get_company_tickers()
print(datas)
print("=======" * 20)
# for idx, row in datas.iterrows():
#     # print(row)
#     c = Company(row["ticker"])
#     print(f"{idx}번 : {c.name} ({c.cik})")


# 2. 기업 제출 이력(특정 기업이 낸 모든 공시서류 목록. 10-K, 13F, Form 4 등 원하는 문서를 찾기)
c = Company(datas.iloc[0]["ticker"])
d = Company(datas.iloc[0]["ticker"]).data
print(json.dumps(vars(d), indent=2, ensure_ascii=False, default=str))
print(d.cik)  # 1730168
print(d.name)  # Broadcom Inc.
print(d.entity_type)  # operating
print(d.sic)  # 3674
print(d.sic_description)  # Semiconductors & Related Devices
print(d.tickers)  # ['AVGO']
print(d.exchanges)  # ['Nasdaq']
print(d.ein)  # 352617337
print(d.category)  # Large accelerated filer
print(d.fiscal_year_end)  # 1101
print(d.phone)  # 650-427-6000
print(d.former_names)  # [{'name': 'Broadcom Ltd', 'from': '2018-02-06', 'to': '2018-03-09'}]
print(d.business_address)
print(d.mailing_address)

print("=======" * 20)
f = c.get_filings(form="10-K").latest(1)
print(f)

print("=======" * 20)
fin = c.get_financials()
print(fin)
