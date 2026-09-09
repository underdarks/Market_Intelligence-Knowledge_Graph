### 플로우

paragraphs.py 문서 전체에서 후보 문단 추출 (아직 관계인지 판정 안 됨)
↓
judge.py 후보 문단이 진짜 위탁 관계 서술인지 LLM 판정 (여기서 confidence 결정)
↓
load_relations.py 판정 통과한 것만 그래프에 적재

#### 독립성, 유연한 설계

- paragraphs.py는 EDGAR API만 알면 됨 (그래프도 LLM도 몰라도 됨)
- judge.py는 LLM만 알면 됨 (EDGAR 호출 방식도, Neo4j도 몰라도 됨)
- load_relations.py는 Neo4j만 알면 됨
