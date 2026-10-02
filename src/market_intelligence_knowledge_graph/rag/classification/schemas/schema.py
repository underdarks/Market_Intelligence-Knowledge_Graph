from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    """질문 유형. 미지원 유형도 명시해야 분류기가 가까운 지원 유형으로 우겨넣지 않는다."""

    T1 = "T1"  # 기업 이벤트/실적 요약: "하닉 2분기 실적 요약해줘"
    T2 = "T2"  # 원인 분석: "삼전 주가 왜 빠졌어?"
    T3 = "T3"  # 영향 경로: "TSMC 감산하면 어디가 영향 받아?"
    T4 = "T4"  # 정형 지표 조회/비교: "삼전 vs 하닉 영업이익률 비교"
    T5 = "T5"  # 매크로 지표 해석 (미지원 안내): "금리 오르면 반도체에 뭐가 문제야?"
    T6 = "T6"  # 개념 설명 (폴백): "PER이 뭐야?"
    T7 = "T7"  # 매수 추천/가격 예측 (거절): "엔비디아 지금 사도 돼?"
    T8 = "T8"  # 범위 밖 (거절): "오늘 점심 뭐 먹지?"
    T9 = "T9"  # 스크리닝 (현재 미지원 안내): "PER 10 이하 반도체주 찾아줘"
    T10 = "T10"  # 가설 검증 (현재 미지원 안내): "HBM 수요 꺾이면 하닉이 불리해질까?"


class ExtractedMention(BaseModel):
    """LLM이 유저 질문에서 추출한 회사 관련 단어 정보를 담는 클래스(LLM이 문장에서 찾아낸 '회사 이름 언급' 1건)"""

    # model_config: 이 모델의 기본 동작 방식을 설정하는 옵션
    # frozen=True: 한 번 만들어진 객체는 내부 값을 절대 수정할 수 없게 함 (불변 객체로 만듦)
    model_config = ConfigDict(frozen=True)

    # surface: 유저가 질문에 '입력한 그대로'의 단어 (원문 텍스트)
    # (예: "마이크런 실적 어때?" -> surface = "마이크런") 💡 용도: 질문 원문에 실제 이 단어가 존재하는지 검증할 때 사용
    surface: str

    # guess: 오타나 줄임말일 때 LLM이 "아, 아마 이걸 의미했겠구나" 하고 추측한 정식 명칭
    # str | None = None : 값이 없을 수도 있음(None이 기본값) 예: surface가 "마이크런"이면 guess = "마이크론", 오타가 없으면 None)
    guess: str | None = None


class Classification(BaseModel):
    """유저 질문을 분석한 최종 분류 결과 클래스(질문 분류기)"""

    # 이 객체도 마찬가지로 생성된 후 값을 변경할 수 없도록 불변(frozen)으로 설정
    model_config = ConfigDict(frozen=True)

    # type: 질문의 유형 (예: 단일 회사 질문, 비교 질문, 일반 질문 등)
    type: QuestionType

    # confidence: 분류 결과에 대한 LLM/분류기의 확신도(점수)
    # Field(ge=0.0, le=1.0): 0.0 이상(Greater than or Equal), 1.0 이하(Less than or Equal)
    # 💡 용도: 0.0 ~ 1.0 범위를 벗어난 값이 들어오면 Pydantic이 자동으로 에러(ValidationError)를 발생시킴
    confidence: float = Field(ge=0.0, le=1.0)

    # mentions: 질문 안에서 뽑아낸 회사 언급 목록 (ExtractedMention 객체들의 튜플)
    # tuple[..., ...] = () : 개수가 정해지지 않은 불변 튜플 형태이며, 기본값은 빈 튜플 ()
    # 💡 용도: 리스트가 아닌 불변(tuple) 구조를 사용하여 안전하게 관리함 만약 비어 있다면(""), 특정 회사를 짚어서 물어본 게 아니라고 판단하여 질문 전체를 분석함
    mentions: tuple[ExtractedMention, ...] = ()
