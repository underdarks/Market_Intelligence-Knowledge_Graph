from itertools import chain
from time import sleep

from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.adapters.dart_adapter import DartCompanyAdapter
from market_intelligence_knowledge_graph.config import SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.adapters.edgar_adapter import EdgarCompanyAdapter
from market_intelligence_knowledge_graph.graph.load_companys import load_companies
from market_intelligence_knowledge_graph.sample.targets import TARGET_KR_COMPANYS, TARGET_US_COMPANYS

"""
NVDA (엔비디아): AI 연산의 두뇌 역할을 하는 GPU 가속기 시장을 독점하는 인공지능 혁명의 대장주입니다.
AMD (어드밴스드 마이크로 디바이시즈): CPU와 GPU를 모두 다루며 엔비디아의 독점을 견제할 유일한 대안으로 꼽히는 설계 기업입니다.
AVGO (브로드컴): AI 데이터 센터의 방대한 데이터를 통제하는 초고속 네트워크 칩 분야의 절대 강자입니다.
MRVL (마벨 테크놀로지): 데이터 센터와 인프라의 내부 통신을 연결하는 초고속 데이터 전송 및 광통신 반도체 전문 기업입니다.
QCOM (퀄컴): 모바일 칩 세계 1위이자 스마트폰과 PC 자체에서 AI를 구동하는 온디바이스 AI 시장의 선두 주자입니다.
TSM (TSMC): 엔비디아, 애플 등 빅테크의 최첨단 칩을 도맡아 제작하는 세계 최대의 반도체 위탁 생산(파운드리) 기업입니다
"""


#Company 적재 파이프라인
def main() -> None:
    # 1. DB 연결
    db.verify()  # 연결확인

    # 2. 어뎁터
    edgar_company = EdgarCompanyAdapter()
    dart_company = DartCompanyAdapter()

    nodes = []

    # 어뎁터 합침(최적화된 방식 : 리스트를 미리 만들지 않고, 순회할 때 하나씩 꺼내쓰는 제너레이터)
    targets = chain(
        ((edgar_company, t) for t in TARGET_US_COMPANYS), ((dart_company, c["corp_code"]) for c in TARGET_KR_COMPANYS)
    )
    """
        # 방법1
        # targets = [(edgar_company, t) for t in TARGET_US_COMPANYS] + [
        #     (dart_company, c["corp_code"]) for c in TARGET_KR_COMPANYS
        # ]

        # 방법2
        # targets = [
        #     *[(edgar_company, t) for t in TARGET_US_COMPANYS],
        #     *[(dart_company, c["corp_code"]) for c in TARGET_KR_COMPANYS],
        # ]
    """

    # 3. 국가별 TARGETS 돌면서 DB 저장
    for company_adapter, id in targets:
        try:
            node = company_adapter.load(id=id)
            if node is None:
                print("skip")
                continue

            nodes.append(node)
            print(f"[EXTRACT] {id}: {node['entity_id']} {node['name']}")
        except Exception as e:
            print(f"[ERR] {id}: {type(e).__name__} {e}")
            continue
        finally:
            sleep(SEC_RATE_LIMIT_SLEEP)

    # 3. 적재
    cnt: int = load_companies(nodes)
    print(f"\n[LOAD] {cnt}개 노드 적재 완료")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
