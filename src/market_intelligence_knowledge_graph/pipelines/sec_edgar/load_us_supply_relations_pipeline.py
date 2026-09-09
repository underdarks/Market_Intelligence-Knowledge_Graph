import time

from edgar import Company, set_identity
from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.config import SEC_IDENTITY, SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.extraction.sec_edgar.judge import judge_paragraph
from market_intelligence_knowledge_graph.extraction.sec_edgar.sec_edgar_text_extraction import get_company_mentions
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import JudgedRelation, ParagraphMention
from market_intelligence_knowledge_graph.graph.load_relations import load_supply_relation
from market_intelligence_knowledge_graph.sample.targets import TARGET_PAIRS
from market_intelligence_knowledge_graph.utils.entity import to_entity_id

set_identity(SEC_IDENTITY)

"""
judge_supply_relations.py(이 파일)는 아래 세 모듈을 순서대로 호출해서 "공급 위탁 관계를 찾아 그래프에 저장한다"는 전체 흐름을 지휘하는 오케스트레이션 역할.

1. paragraphs.py (get_company_mentions)
   역할: SEC EDGAR에서 원본 10-K 문서를 받아와서, 특정 회사(예: TSMC)를
        언급한 문단만 grep으로 뽑아낸다.
   입력: 문서 주체 티커(예: "AVGO"), 찾을 대상의 여러 표기(예: ["TSMC", "Taiwan Semiconductor"])
   출력: ParagraphMention 리스트 (문단 원문 + accession, file_date 같은 메타데이터)
   이 파일이 아는 것: EDGAR API, edgartools 사용법, grep 검색
   이 파일이 모르는 것: 이 문단이 진짜 위탁 관계인지(=LLM 판정), 그래프 구조(=Neo4j)

2. judge.py (judge_paragraph)
   역할: 문단 하나를 LLM(OpenAI)에 보내서 "이게 진짜 제조/공급 위탁 관계를
        서술하는 문단인가"를 판정하고, confidence 등급(disclosed/stated/none)을 매긴다.
   입력: ParagraphMention 하나, 대상 회사의 티커·entity_id
   출력: 관계로 인정되면 JudgedRelation(Evidence+Relation 정보 포함), 아니면 None
   이 파일이 아는 것: LangChain, LLM 프롬프트 설계, Pydantic 구조화 출력
   이 파일이 모르는 것: 이 문단을 어디서 가져왔는지(=EDGAR), 그래프에 어떻게 저장되는지(=Neo4j)

3. load_relations.py (load_supply_relation)
   역할: 판정된 관계(JudgedRelation)를 받아서 Neo4j에 실제로 저장한다.
        Company 두 개를 MATCH하고, 그 사이에 SupplyRelation 노드를 만들고,
        근거가 된 Evidence 노드를 SUPPORTED_BY로 연결한다.
   입력: JudgedRelation 하나
   출력: 없음(그래프에 부수효과로 저장만 함)
   이 파일이 아는 것: Cypher 쿼리, Neo4j 드라이버, 우리 그래프 스키마
   이 파일이 모르는 것: 이 관계를 어떻게 판정했는지(=LLM), 원본 문서가 어디서 왔는지(=EDGAR)

이렇게 세 파일이 각자 하나의 외부 시스템(EDGAR / LLM / Neo4j)만 알도록 나눈 이유:
나중에 LLM을 OpenAI에서 다른 걸로 바꾸거나, EDGAR 대신 DART를 붙이거나,
Neo4j 쿼리 구조를 바꿔야 할 때 — 그 파일 하나만 고치면 되고 나머지 둘은
안 건드려도 되게 하기 위함(책임 분리)
"""


# SEC_EDGAR 기반 SupplyRelation/Evidence 적재 파이프라인
def main() -> None:
    db.verify()

    tickers = set()
    for pair in TARGET_PAIRS:
        tickers.add(pair["from_ticker"])
        tickers.add(pair["to_ticker"])

    # ticker 기반 entity id 캐싱
    entity_id_chache = {ticker: to_entity_id(ticker) for ticker in tickers}

    # AVGO(AMD, NVDA, QCOM등)가 10-k에서 특정 회사(ex. "TSM")을 언급한거 찾기
    for pair in TARGET_PAIRS:
        # 언급된 문단(ex. AVGO 10-K에서 TSMC 언급한 문단)
        paragraphs: list[ParagraphMention] = get_company_mentions(
            from_ticker=pair.get("from_ticker"), to_company_aliases=pair.get("aliases")
        )
        if not paragraphs:
            print(f"[SKIP] {pair['from_ticker']}: 언급 문단 없음")
            continue

        for paragraph in paragraphs:
            try:
                judged_relation: JudgedRelation | None = judge_paragraph(
                    paragraph=paragraph, to_ticker=pair["to_ticker"], to_entity_id=entity_id_chache[pair["to_ticker"]]
                )

                # LLM이 "이 문단은 위탁 관계 서술이 아니다"라고 판정하면 None이 옴(그래프에 만들 게 없으니 다음 문단으로 넘어감)
                if judged_relation is None:
                    continue

                # judge_paragraph는 to_entity_id까지만 채워서 돌려줌 from_entity_id는 파이프라인(여기)이 캐시에서 꺼내 채움
                judged_relation.from_entity_id = entity_id_chache[pair["from_ticker"]]

                # SupplyRelation(공급관계) / Evidence(근거) Neo4j에 저장
                load_supply_relation(
                    judgedRelation=judged_relation,
                )

                print(
                    f"[LOAD] {judged_relation.from_ticker} -> "
                    f"{judged_relation.to_ticker} ({judged_relation.relation.confidence})"
                )
            except Exception as e:
                print(f"[ERR] {pair['from_ticker']} 저장 실패: {type(e).__name__} {e}")
            finally:
                time.sleep(SEC_RATE_LIMIT_SLEEP)

    print("완료")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
