from contextlib import contextmanager

from neo4j import Driver, GraphDatabase, Session

from market_intelligence_knowledge_graph.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

""""""
_driver: Driver = GraphDatabase.driver(uri=NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


@contextmanager
def session():
    s: Session = _driver.session()
    try:
        yield s
    finally:
        s.close()


def verify() -> None:
    _driver.verify_connectivity()


def close() -> None:
    _driver.close()
