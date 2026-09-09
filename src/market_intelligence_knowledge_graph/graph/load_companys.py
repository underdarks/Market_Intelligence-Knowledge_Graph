from market_intelligence_knowledge_graph.db import session

# 멱등성 보장하는 Company 적재 쿼리
_MERGE_COMPANY_QUERY = """
UNWIND $rows AS row
MERGE (c:Company {entity_id: row.entity_id})
ON CREATE SET c.created_at = datetime()
SET c += row,
    c.updated_at = datetime()
RETURN count(c) AS n
"""


# 여러 노드를 한 트랜잭션으로 적재. UNWIND라 왕복이 1회뿐
def load_companies(nodes: list[dict]) -> int:
    if not nodes:  # 노드가 비어있다면
        return 0

    with session() as s:  # 커넥션 풀에서 TCP 커넥션하나 가져옴
        # s.execute_write(transaction_function=lambda tx: ... )
        # : Neo4j에게 "지금부터 쓰기(Write) 트랜잭션을 시작할게"라고 선언합니다. 내부의 익명 함수(lambda tx)를 통해 트랜잭션 객체(tx)를 제어합니다.

        """
        res = s.execute_write(lambda tx: tx.run(_MERGE_COMPANY, rows=nodes))
        return res.single()   # ← 여기서 터짐
        - 왜 이게 문제냐면: tx.run()이 반환하는 Result 객체는 트랜잭션이 열려 있는 동안에만 유효해.
        - execute_write는 람다 함수가 끝나는 순간 트랜잭션을 커밋하고 닫아버려. 그러니까 Result를 람다 밖으로 꺼내서 나중에 .single()을 부르면, 그땐 이미 연결이 끊긴 뒤라서 "트랜잭션이 스코프 밖이다"라고 에러가 나.
        -> 그래서 single()을 람다 안에서 끝내야함(아래 코드 참고)
        """

        return s.execute_write(
            transaction_function=lambda tx: tx.run(query=_MERGE_COMPANY_QUERY, rows=nodes).single()["n"]
        )
    