from pymongo import MongoClient
from pymongo.database import Database
from market_intelligence_knowledge_graph.config.config import MONGO_URI, MONGO_DB_NAME

_client: MongoClient | None = None


# MongoDB DB 객체 반환, 커넥션 없으면 새로 만들고 있으면 재사용
def get_mongodb() -> Database:
    global _client  # 함수 내부에서 함수 외부에 있는 전역 변수(Global Variable) _client를 직접 수정하겠다고 선언한다는 의미
    if _client is None:
        """
        MongoClient 자체가 이미 커넥션 풀을 관리해줌 (Neo4j의 GraphDatabase.driver와 비슷한 개념
        MongoClient(MONGO_URI)가 호출되는 순간 커넥션 풀이 "준비"되지만, 실제 TCP 연결은 첫 번째 실제 쿼리(insert, find 등)가 실행될 때 지연 생성(lazy connection)됨
        get_db()를 여러 번 호출해도 _client가 이미 있으면 같은 풀을 계속 재사용함(Neo4j의 session()이 실제로는 드라이버가 미리 확보해둔 풀에서 커넥션을 "빌려오는" 것과 비슷한 개념)
        """
        _client = MongoClient(host=MONGO_URI)
    # client["db이름"] 형태로 데이터베이스 객체를 꺼냄, 실제로 컬렉션에 넣을 땐 db["컬렉션이름"] 또는 db.컬렉션이름 으로 접근
    return _client[MONGO_DB_NAME]


# 연결 검증
def verify() -> None:
    db = get_mongodb()
    db.command("ping")  # ping은 MongoDB가 응답하는지만 확인하는 가장 가벼운 명령, 실패시 예외 발생
    print("MongoDB Connect 성공")


# 커넥션 종료
def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
