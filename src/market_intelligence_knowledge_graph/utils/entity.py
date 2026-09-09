from edgar import Company


# SEC EDGAR, Dart id를 받아서 그래프의 entity_id 형식으로 변환. 예: "AVGO" -> "cik:0001730168"
def to_entity_id(id: str, country: str = "us") -> str:
    if country == "us":
        cik = Company(cik_or_ticker=id).cik
        return f"cik:{str(cik).zfill(10)}"
    elif country == "kr":
        return f"dart:{id}"
    else:
        raise ValueError(f"지원하지 않는 country: {country}")


# DART의 YYYYMMDD를 EDGAR 형식(YYYY-MM-DD)으로 변환
def normalize_dart_date(rcept_dt: str) -> str:
    return f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
