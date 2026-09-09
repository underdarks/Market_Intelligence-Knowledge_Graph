### 프로젝트 폴더 구조(phase 1)

mikg/
├── pyproject.toml
├── uv.lock
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
│
├── neo4j/ # L3 (Data Platform) — 볼륨 마운트만 존재
│ ├── data/
│ ├── logs/
│ └── plugins/
│
├── src/
│ └── mikg/
│ ├── **init**.py
│ ├── config.py # 공통 설정
│ ├── db.py # L3 — Neo4j 드라이버
│ │
│ ├── sources/ # L1 (Source) — 소스별 원본 접근
│ │ ├── **init**.py
│ │ └── edgar/
│ │ ├── **init**.py
│ │ ├── client.py # edgartools 래핑, set*identity 등
│ │ └── search.py # 전문검색, grep 등
│ │
│ ├── adapters/ # L4 앞단 — 소스 원본 → 공통 스키마 변환
│ │ ├── **init**.py
│ │ ├── base.py # CompanyAdapter 추상 클래스
│ │ └── edgar_adapter.py # EdgarAdapter (오늘 만든 extract_company 로직)
│ │
│ ├── extraction/ # L4 (Data Processing) — 관계 추출·판정
│ │ ├── **init**.py
│ │ └── relation_judge.py # confidence 판정 (다음 단계에서 작성)
│ │
│ ├── ontology/ # L5 (Ontology) — 스키마 정의 자체를 코드로
│ │ ├── **init**.py
│ │ ├── schema.py # 노드/엣지 타입, 제약조건 Cypher
│ │ └── constants.py # confidence 등급, entity_id 접두사 규칙 등
│ │
│ ├── graph/ # L5~L3 사이 — 적재·조회
│ │ ├── **init**.py
│ │ ├── load.py # MERGE 적재 (오늘 만든 load_companies)
│ │ └── queries.py # 대표 순회 쿼리 모음
│ │
│ ├── rag/ # L6 (AI & Reasoning) — 아직 비어있음, 자리만
│ │ └── **init**.py
│ │
│ └── pipelines/ # 실행 스크립트 (파이프라인 오케스트레이션)
│ ├── **init**.py
│ └── load_companies.py
│
├── tests/
│ └── **init**.py
│
└── docs/
├── SEC_EDGAR_API*레퍼런스.md
├── MIKG*온톨로지*스키마.md
└── MIKG*데이터확보*조사결과.md
