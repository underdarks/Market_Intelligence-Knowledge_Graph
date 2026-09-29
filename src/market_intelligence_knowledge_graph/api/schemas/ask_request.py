from pydantic import BaseModel, ConfigDict, Field, field_validator
from market_intelligence_knowledge_graph.config.rag_api import get_question_max_length


class AskRequest(BaseModel):
    # 공백 제거 옵션 (문자열 앞뒤 공백을 자동으로 trim)
    model_config = ConfigDict(str_strip_whitespace=True)

    # 최소 1자 이상이어야 함 (빈 문자열 "" 방지)
    question: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)

    @field_validator("question")  # question 필드의 값을 검증하는 전용 함수라고 pydantic에 등록
    @classmethod  # 클래스 메서드
    def _limit_length(cls, value: str) -> str:
        max_length = get_question_max_length()

        if len(value) > max_length:
            raise ValueError(f"질문은 {max_length}자 이하여야 합니다")
        return value
