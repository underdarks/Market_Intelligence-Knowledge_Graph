"""
EDGAR statement_type 추론 규칙 — 검증 과정 기록

## 배경
DART는 sj_div 필드로 BS/IS/CF를 명시적으로 알려주는데,
EDGAR는 그런 필드가 없어서 직접 규칙을 만들어야 했음.

## 검증 방법
이미 뜻을 아는 계정과목 몇 개를 골라서 period_type이 어떻게 나오는지 직접 확인:

  us-gaap:Revenues                                      → duration  (매출, IS)
  us-gaap:CostOfRevenue                                 → duration  (매출원가, IS)
  us-gaap:NetIncomeLoss                                 → duration  (순이익, IS)
  us-gaap:Assets                                        → instant   (총자산, BS)
  us-gaap:Liabilities                                   → instant   (총부채, BS)
  us-gaap:StockholdersEquity                            → instant   (자본, BS)
  us-gaap:CashAndCashEquivalentsAtCarryingValue          → instant   (현금 잔액, BS)
  us-gaap:NetCashProvidedByUsedInOperatingActivities     → duration  (영업활동현금흐름, CF)

## 발견한 규칙
- instant  → 항상 BS (특정 시점의 잔액이라는 의미와 일치)
- duration → IS 또는 CF 둘 다 가능 (기간 동안의 흐름이라는 점은 같음)
  → duration 중에서 CF만 골라내려면 concept 이름에 "ProvidedBy"/"UsedIn" 패턴이 있는지로 판별
    (CF 항목은 "~로부터 제공된/~에 사용된 현금"이라는 서술 방식을 따르기 때문)

## 실전 데이터로 재검증 (NVIDIA, 최근 5년, us-gaap만 필터링한 9819행 기준)
  Counter({'IS': 5280, 'BS': 4377, 'CF': 162})

  CF로 분류된 concept 3개가 실제로 다 현금흐름표 핵심 항목이었음:
    us-gaap:NetCashProvidedByUsedInOperatingActivities  (영업활동)
    us-gaap:NetCashProvidedByUsedInInvestingActivities  (투자활동)
    us-gaap:NetCashProvidedByUsedInFinancingActivities  (재무활동)

  → "ProvidedBy"/"UsedIn" 패턴 규칙이 정확히 이 3개만 걸러내고, 다른 오탐 없음을 확인
  → UNKNOWN(규칙에 안 걸리는 것)도 0건, 규칙이 이 데이터셋에서 완전히 커버됨

## 확정된 규칙 (_infer_statement_type 함수에 반영됨)
  period_type == "instant"                        → BS
  period_type == "duration" AND "ProvidedBy"/"UsedIn" 포함 → CF
  나머지 duration                                    → IS
  그 외(이론상 없어야 함)                              → UNKNOWN (방어용)
"""