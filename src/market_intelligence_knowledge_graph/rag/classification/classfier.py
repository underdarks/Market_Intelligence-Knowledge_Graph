from pyclbr import Class
from typing import Protocol

from market_intelligence_knowledge_graph.rag.classification.schemas.schema import Classification, QuestionType


# 질문 분류기
class QuestionClassifier(Protocol):
    async def classify(self, question: str) -> Classification: ...


class StubQuestionClassifier:

    async def classify(self, question: str) -> Classification:
        return Classification(type=QuestionType.T1, confidence=1.0, mentions=())
