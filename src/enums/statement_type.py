# statement_type("BS"/"IS"/"CF")을 edgartools가 쓰는 이름으로 매핑
_STATEMENT_TYPE_MAP: dict[str, str] = {
    "BS": "BalanceSheet",
    "IS": "IncomeStatement",
    "CF": "CashFlow",
}


def get_statement_type(key) -> str:
    try:
        return _STATEMENT_TYPE_MAP[key]
    except KeyError:
        raise ValueError(f"지원하지 않는 statement_type: {key}") from None
