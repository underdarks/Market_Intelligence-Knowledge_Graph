from opensearchpy import OpenSearch

from market_intelligence_knowledge_graph.config.config import OPENSEARCH_HOST, OPENSEARCH_PORT

_client: OpenSearch | None = None


# OpenSearch 클라이언트 반환, 커넥션 없으면 새로 만들고 있으면 재사용
def get_opensearch() -> OpenSearch:
    global _client  # 함수 내부에서 함수 외부에 있는 전역 변수(Global Variable) _client를 직접 수정하겠다고 선언한다는 의미
    if _client is None:
        _client = OpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            use_ssl=False,  # 로컬 Docker, DISABLE_SECURITY_PLUGIN=true라 SSL 없음
            verify_certs=False,  # 위와 같은 이유로 인증서 검증 불필요
        )

    return _client


# 연결 검증
def verify() -> None:
    client = get_opensearch()
    health = client.cluster.health()  # 헬스체크
    print(f"OpenSearch Connect 성공 (status: {health['status']})")


# 커넥션 종료
def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


if __name__ == "__main__":
    verify()
    close()
