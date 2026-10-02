from pydantic import BaseModel, ConfigDict, Field, field_validator

from market_intelligence_knowledge_graph.config.api import get_api_settings
from market_intelligence_knowledge_graph.rag.schemas.answer_request import AnswerRequest, UserLevel


class AskRequest(BaseModel):
    """POST /ask 요청 본문 DTO. 서비스 계약(AnswerRequest)과 분리해서 API 형식이 바뀌어도 RagService는 안 바뀌게 한다."""

    model_config = ConfigDict(
        extra="forbid",  # 모르는 필드가 오면 422: 클라이언트 오타를 조용히 무시하지 않음
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1)
    selected_entity_ids: list[str] = Field(
        default_factory=list
    )  # list: JSON 배열을 받기 위함. default_factory: 요청마다 새 빈 리스트 (공유 가변 기본값 방지)
    level: UserLevel = UserLevel.INTERMEDIATE

    @field_validator("question")  # question 필드 검증 후 추가로 실행되는 사용자 정의 검증
    @classmethod
    def _check_max_length(cls, value: str) -> str:
        # 상한을 클래스 정의 시점이 아니라 검증 시점에 config에서 읽음 (하드코딩 금지)
        limit = get_api_settings().question_max_length
        if len(value) > limit:
            raise ValueError(f"질문은 {limit}자 이하여야 합니다")  # pydantic이 422로 변환
        return value

    def to_answer_request(self) -> AnswerRequest:
        return AnswerRequest(
            question=self.question,
            selected_entity_ids=tuple(self.selected_entity_ids),
            level=self.level,
        )
