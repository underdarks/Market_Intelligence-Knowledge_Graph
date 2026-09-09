import requests
from collections import Counter

KEY = "3804b422a767ab11da3156147a89fbcd2f5374bd"

r = requests.get(
    "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json",
    params={
        "crtfc_key": KEY,
        "corp_code": "00126380",  # 삼성전자
        "bsns_year": "2025",
        "reprt_code": "11011",  # 사업보고서로 추정(확인 필요)
    },
)
data = r.json()
print(data["status"], data.get("message"))
print(len(data.get("list", [])))
if data.get("list"):
    print(data["list"][0])
    print(list(data["list"][0].keys()))


print("BS외 IS,CF 확인")
print("=====" * 20)

items = data["list"]
# sj_div별로 몇 개씩 있는지

sj_counts = Counter(item["sj_div"] for item in items)
print(sj_counts)

# 각 sj_div의 account_nm 목록
for sj_div in sj_counts:
    accounts = [item["account_nm"] for item in items if item["sj_div"] == sj_div]
    print(f"\n{sj_div}: {accounts}")

bs_items = [item for item in items if item["sj_div"] == "BS"]
for item in bs_items:
    print(item["account_nm"], item["fs_div"], item["thstrm_amount"])


print("CF 확인")
print("=====" * 20)
r2 = requests.get(
    "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
    params={
        "crtfc_key": KEY,
        "corp_code": "00126380",
        "bsns_year": "2025",
        "reprt_code": "11011",
        "fs_div": "CFS",  # 연결재무제표 지정 (이 API는 필수 파라미터일 수 있음)
    },
)
data2 = r2.json()
print(data2.get("status"), data2.get("message"))
if data2.get("list"):
    sj_counts2 = Counter(item["sj_div"] for item in data2["list"])
    print(sj_counts2)

print("SCE(105개)와 CIS(13개) 확인")
print("=====" * 20)
sce_items = [item for item in data2["list"] if item["sj_div"] == "SCE"]
print(sce_items[0])
print(set(item["account_nm"] for item in sce_items))

cis_items = [item for item in data2["list"] if item["sj_div"] == "CIS"]
print(cis_items[0])


