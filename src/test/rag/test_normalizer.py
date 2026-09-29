# test/rag/entity_linking/test_normalizer.py
import pytest

from market_intelligence_knowledge_graph.rag.entity_linking.normalizer import normalize, squash


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("QUALCOMM INC/DE", "qualcomm"),
        ("NVIDIA CORP/CA", "nvidia"),
        ("SAMSUNG ELECTRONICS CO,.LTD", "samsung electronics"),
        ("DB HiTek Co.,LTD", "db hitek"),
        ("HANMI Semiconductor CO., LTD.", "hanmi semiconductor"),
        ("SAMSUNG ELECTRO-MECHANICS CO.,LTD", "samsung electro mechanics"),
        ("Marvell Technology, Inc.", "marvell technology"),
        ("TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD", "taiwan semiconductor manufacturing"),
        ("주식회사 DB하이텍", "db하이텍"),
        ("삼성전자(주)", "삼성전자"),
        ("에스케이하이닉스(주)", "에스케이하이닉스"),
        ("ＮＶＩＤＩＡ", "nvidia"),
        ("SK 하이닉스", "sk 하이닉스"),
        ("risk and/or return", "risk and or return"),  # 소문자 "/or"는 지워지면 안 됨
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_squash():
    assert squash("SK 하이닉스") == "sk하이닉스"
