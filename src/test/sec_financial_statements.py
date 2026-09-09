from edgar import Company, set_identity

set_identity("MIKG Research test@example.com")

c = Company("NVDA")
# print([attr for attr in dir(c) if not attr.startswith("_")])


# 1. 가장 가공된 형태부터
print("가공 형태")
print("===" * 20)
income = c.income_statement
print(type(income))
print(income)

print("원시 fact")
print("===" * 20)
# 2. 원시 facts도 확인
facts = c.get_facts()
print(type(facts))
print(dir(facts))


print("fact DataFrame 출력")
print("===" * 20)
# 3. DataFrame으로도 확인
df = facts.to_dataframe()
print(df.shape)
print(df.columns.tolist())
print(df.head(10))

print("실제 매출 데이터 확인")
print("===" * 20)
revenue_rows = df[df["concept"].str.contains("Revenue", case=False, na=False)]
print(revenue_rows["concept"].unique())
print(revenue_rows[revenue_rows["fiscal_period"] == "FY"].tail(10))

print("Non-GAAP 확인")
print("===" * 20)
# Non-GAAP(회사 커스텀 태그) 존재 여부
custom = df[df["concept"].str.contains("nvda:", case=False, na=False)]
print(custom["concept"].unique()[:20])

print("세그먼트 확인")
print("===" * 20)
# 세그먼트별 매출 존재 여부
segment = df[df["concept"].str.contains("Segment", case=False, na=False)]
# print(segment[["concept", "label"]].drop_duplicates())

segment_dim = df[df["concept"] == "us-gaap:Revenues"]
print(segment_dim.columns.tolist())  # dimension 관련 컬럼이 있는지
print(len(segment_dim))  # 방금 본 10개보다 훨씬 많으면 dimension별로 쪼개진 것

print("부분별 매출액 확인")
print("===" * 20)
segment_dim = df[df["concept"] == "us-gaap:Revenues"]
print(segment_dim[["value", "period_start", "period_end", "fiscal_year", "fiscal_period"]].to_string())

print(segment_dim["label"].unique())


print("EDGAR statement_type 추론 확인")
print("===" * 20)
# concept 이름에 패턴이 있는지 확인
sample_concepts = df["concept"].unique()[:30]
print(sample_concepts)

# period_type과 concept 이름 사이 관계 확인
print(df.groupby("period_type")["concept"].apply(lambda x: x.unique()[:5]))

print("EDGAR statement_type us-gaap 확인")
print("===" * 20)

key_concepts = [
    "us-gaap:Revenues",  # 매출 (IS 항목일 것으로 예상)
    "us-gaap:CostOfRevenue",  # 매출원가 (IS)
    "us-gaap:NetIncomeLoss",  # 순이익 (IS)
    "us-gaap:Assets",  # 총자산 (BS 항목일 것으로 예상)
    "us-gaap:Liabilities",  # 총부채 (BS)
    "us-gaap:StockholdersEquity",  # 자본 (BS)
    "us-gaap:CashAndCashEquivalentsAtCarryingValue",  # 현금 (BS)
    "us-gaap:NetCashProvidedByUsedInOperatingActivities",  # 영업활동현금흐름 (CF일 것으로 예상)
]

for concept in key_concepts:
    match = df[df["concept"] == concept]
    if len(match) > 0:
        print(concept, "→", match["period_type"].unique())
    else:
        print(concept, "→ 데이터 없음")
