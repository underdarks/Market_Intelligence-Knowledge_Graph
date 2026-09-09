import requests
import zipfile
import io

url = "https://opendart.fss.or.kr/api/corpCode.xml"
params = {"crtfc_key": "3804b422a767ab11da3156147a89fbcd2f5374bd"}
r = requests.get(url, params=params)

# ZIP 파일인지 확인
f = io.BytesIO(r.content)
zfile = zipfile.ZipFile(f)
# print(zfile.namelist())  # 안에 어떤 파일이 들어있는지
xml_content = zfile.read("CORPCODE.xml").decode("utf-8")
print(len(xml_content))
print(xml_content[:1000])
if "00126380" in xml_content:
    # print("찾음")
    idx = xml_content.find("00126380")
    # print(xml_content[max(0, idx - 100) : idx + 300])


import requests

KEY = "3804b422a767ab11da3156147a89fbcd2f5374bd"

# 1. 기업개황
r1 = requests.get("https://opendart.fss.or.kr/api/company.json", params={"crtfc_key": KEY, "corp_code": "00126380"})
print("=== company.json ===")
print(r1.json())

print("반도체 관련주")
print("===" * 20)
for name, expected_stock_code in [
    ("삼성전자", "005930"),
    ("SK하이닉스", "000660"),
    ("DB하이텍", "000990"),
    ("한미반도체", "042700"),
    ("삼성전기", "009150"),
]:
    idx = xml_content.find(f"<stock_code>{expected_stock_code}</stock_code>")

    if idx != -1:
        print(xml_content[max(0, idx - 250) : idx + 50])
        print()
