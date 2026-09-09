# 파일럿 단계에서 검증용으로 고른 표본 데이터

# 전체 파일럿 대상 기업 (Company 노드 생성)
TARGET_US_COMPANYS = ["AVGO", "AMD", "NVDA", "QCOM", "MRVL", "TSM", "MU", "SNDK"]
# DART 파일럿 대상 기업 (한국 반도체 생태계, 미국 구성과 대칭)
# corp_code는 corpCode.xml에서 실측 확인됨 (2026-09-05)
TARGET_KR_COMPANYS = [
    {"corp_code": "00126380", "name": "삼성전자", "role": "memory_idm"},  # Micron/Sandisk 대응
    {"corp_code": "00164779", "name": "SK하이닉스", "role": "memory_idm"},  # HBM 세계 1위
    {"corp_code": "00160843", "name": "DB하이텍", "role": "foundry"},  # TSMC 대응(8인치 중심)
    {"corp_code": "00161383", "name": "한미반도체", "role": "equipment"},  # Lam Research 대응
    {"corp_code": "00126371", "name": "삼성전기", "role": "components"},  # 반도체 기판/부품
]


# DESIGNS/SELLS 추출 대상 (judge_products_pipeline.py)
# 파운드리(TSM)는 제외 — 설계/판매가 아니라 PERFORMS 대상이므로 (Company)-[:DESIGNS|SELLS]->(Product)
TARGET_TICKERS = ["NVDA", "AVGO", "AMD", "QCOM", "MU", "SNDK"]


# OUTSOURCES_TO 판정 대상 (judge_supply_relations_pipeline.py)
# MRVL, MU, SNDK는 실측으로 TSMC 언급 0건 확인되어 제외
# (Company)-[:FROM]->(SupplyRelation)-[:TO]->(Company) 생성
# (SupplyRelation)-[:SUPPORTED_BY]->(Evidence) 생성
TARGET_PAIRS = [
    {"from_ticker": "AVGO", "to_ticker": "TSM", "aliases": ["Taiwan Semiconductor", "TSMC"]},
    {"from_ticker": "AMD", "to_ticker": "TSM", "aliases": ["Taiwan Semiconductor", "TSMC"]},
    {"from_ticker": "NVDA", "to_ticker": "TSM", "aliases": ["Taiwan Semiconductor", "TSMC"]},
    {"from_ticker": "QCOM", "to_ticker": "TSM", "aliases": ["Taiwan Semiconductor", "TSMC"]},
]


# 회사가 특정 공정/기술을 수행한다는 근거를 회사 공식 문서(20-F 등)에서 직접 확인하는 대상
# derive_process.py(SupplyRelation에서 파생, confidence="inferred")와 달리 문서 원문을 1차 근거로 삼음 (confidence="stated"/"disclosed")
#  Company)-[:PERFORMS]->(Process) 생성, 근거는 엣지 속성에 직접 저장(노드 승격 없음)
MANUAL_PERFORMS_US = [
    {"ticker": "TSM", "form": "20-F", "keyword": "CoWoS", "process_type": "advanced_packaging"},
]

# 한국 dart (Company)-[:PERFORMS]->(Process) 생성용 수동 큐레이션 데이터(뉴스 기반)
# 추후 자동 추출 파이프라인 구현 예정
MANUAL_PERFORMS_KR = [
    {
        "corp_code": "00126380",  # 삼성전자
        "process_name": "TSV",
        "process_type": "tsv",
        "confidence": "stated",
        "quoted_text": "TSV는 D램 칩을... 미세한 구멍을 뚫어 칩 상하단을 전극으로 연결하는 패키징 기술",
        "source_url": "https://www.sedaily.com/article/20082606",
        "form": "news",
        "as_of_date": "2026-08-23",
    },
    {
        "corp_code": "00164779",  # SK하이닉스
        "process_name": "TSV",
        "process_type": "tsv",
        "confidence": "stated",
        "quoted_text": "TSV는 D램 칩을... 미세한 구멍을 뚫어 칩 상하단을 전극으로 연결하는 패키징 기술",
        "source_url": "https://www.sedaily.com/article/20082606",
        "form": "news",
        "as_of_date": "2026-08-23",
    },
]


# REQUIRES(Product -> Process) 관계의 수동 큐레이션 근거
# EDGAR/DART 둘 다 공시 API로 자동 확보 불가 확인됨(전수조사 완료)
# → 국가 무관하게 뉴스/IR 자료 등에서 사람이 직접 검증한 근거만 등록(추후 뉴스 API 등 검토)
MANUAL_REQUIRES = [
    {
        "product_id": "product:gpus",
        "process_id": "process:advanced_packaging",
        "confidence": "stated",
        "quoted_text": "As we move into Blackwell, we will use largely CoWoS-L",
        "source_url": "https://www.tomshardware.com/tech-industry/nvidia-shifts-to-cowos-l-packaging-for-blackwell-gpu-production-ramp-up",
        "source_type": "news",
        "as_of_date": "2025-01-16",
    },
    {
        "product_id": "product:semiconductor_solutions",
        "process_id": "process:wafer_fabrication",
        "confidence": "disclosed",
        "quoted_text": "approximately 95% of the wafers manufactured by our CMs were produced by TSMC",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1730168/000173016825000121/",
        "source_type": "sec_filing",
        "as_of_date": "2025-12-18",
    },
    {  # 신규
        "product_id": "product:high-bandwidth_memory_(hbm)",
        "process_id": "process:tsv",
        "confidence": "stated",
        "quoted_text": "TSV는 D램 칩을... 미세한 구멍을 뚫어 칩 상하단을 전극으로 연결하는 패키징 기술",
        "source_url": "https://www.sedaily.com/article/20082606",
        "source_type": "news",
        "as_of_date": "2026-08-23",
    },
]
