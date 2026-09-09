from abc import ABC, abstractmethod


# ABC는 파이썬에서는 추상클래스를 만들기위해 반드시 상속받아야하는 내장 클래스이다
class CompanyAdapter(ABC):
    """소스별 원본 데이터를 공통 Company 노드 스키마(dict)로 변환하는 인터페이스"""

    # identifer: 티커 또는 식별자
    @abstractmethod
    def fetch(self, id: str) -> dict:
        """원본 API를 호출해서 raw 데이터를 그대로 반환 (변환 전)"""
        raise NotImplementedError

    @abstractmethod
    def to_node(self, raw: dict) -> dict | None:
        """raw 데이터를 공통 Company 스키마로 변환. 사업회사가 아니면 None"""
        raise NotImplementedError

    # default 메서드
    def load(self, id: str) -> dict | None:
        """fetch + to_node를 이어서 실행하는 공통 흐름. 하위 클래스는 재정의 불필요"""
        return self.to_node(self.fetch(id))
