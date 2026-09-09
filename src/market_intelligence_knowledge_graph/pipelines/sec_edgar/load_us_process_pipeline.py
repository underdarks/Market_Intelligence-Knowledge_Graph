from market_intelligence_knowledge_graph import db
from market_intelligence_knowledge_graph.graph.derive_process import derive_performs_from_supply_relations


# SEC_EDGAR 기반 SupplyRelation의 process_type를 조회해서 Company -[:PERFORMS] -> Process 만드는 파이프라인
def main() -> None:
    db.verify()
    count = (
        derive_performs_from_supply_relations()
    )  # SupplyRelation의 process_type를 조회해서 Company -[:PERFORMS] -> Process 관계 만드는 쿼리
    print(f"완료: {count}건 처리")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.close()
