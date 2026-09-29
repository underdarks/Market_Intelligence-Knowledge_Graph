import re
import unicodedata

# 영문 법인격 토큰. 정규화 후 토큰 단위로 제거한다.
LEGAL_TOKENS = frozenset({"inc", "corp", "corporation", "co", "ltd", "limited", "llc", "plc", "company"})

# 주(州) 코드 접미사 (QUALCOMM INC/DE, NVIDIA CORP/CA).
# 반드시 소문자 변환 전에 지운다. 뒤에 하면 질문 속 "and/or" 같은 표현까지 지워진다.
_STATE_SUFFIX = re.compile(r"/[A-Z]{2}\b")

# 한글 법인격. 특수문자 제거보다 먼저 지운다. 나중에 하면 "(주)"가 "주"만 남아 회사명에 붙는다.
_KO_LEGAL = re.compile(r"\(주\)|주식회사")

# 한글, 영문, 숫자 이외의 모든 문자 (쉼표, 마침표, 하이픈, 슬래시 등)
_NON_WORD = re.compile(r"[^0-9a-z가-힣]+")


def normalize(text: str) -> str:
    """질문/별칭 공용 정규화. 결과는 소문자, 단어는 공백 1개로 구분, 법인격 제거."""
    text = unicodedata.normalize("NFKC", text)  # 전각 문자, ㈜ 등을 표준형으로
    text = _STATE_SUFFIX.sub("", text)
    text = text.lower()
    text = _KO_LEGAL.sub(" ", text)
    text = _NON_WORD.sub(" ", text)  # "CO,.LTD" -> "co ltd"
    tokens = [t for t in text.split() if t not in LEGAL_TOKENS]

    return " ".join(tokens)


def squash(text: str) -> str:
    """정규화 후 공백을 모두 제거. 한글 별칭 매칭용 ("sk 하이닉스" == "sk하이닉스")."""
    return normalize(text).replace(" ", "")
