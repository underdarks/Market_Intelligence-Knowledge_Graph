from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class UserLevel(str, Enum):
    """사용자 레벨. 답변의 추론 깊이를 가른다 (MVP는 중급·고급)."""

    INTERMEDIATE = "intermediate"  # 무슨 일 -> 왜 -> 누가 영향까지(중급)
    ADVANCED = "advanced"  # + 앞으로 -> 뭘 봐야 (고급, 데이터 근거 강화, 반대 근거)


class AnswerRequest(BaseModel):
    """사용자 입력(프롬프트, 추론레벨 등..) DTO"""

    model_config = ConfigDict(
        frozen=True,  # 여러 단계에 그대로 넘기므로 불변
        str_strip_whitespace=True,  # 모든 str 필드의 앞뒤 공백 자동 제거
    )

    question: str = Field(min_length=1)  # 공백 제거 후 빈 문자열이면 생성 시 검증 실패
    selected_entity_ids: tuple[str, ...] = ()  # 되묻기 후 사용자가 고른 회사 ID. 없으면 빈 tuple
    level: UserLevel = UserLevel.INTERMEDIATE  # 기본값: 중급 (UI 설정 없을 때)
