# rag/generation/schema/answer_event.py
#
# 답변 생성 함수(generate_answer)가 "내보내는 이벤트"의 타입 정의.
# 전송 방식(SSE, WebSocket 등)과 무관하게, 생성 로직이 무엇을 내보내는지만 고정한다.
# C3(API 서버)는 이 이벤트를 SSE로 포장만 하면 되고, 생성 로직은 안 건드려도 된다.

from typing import Literal

from pydantic import BaseModel


class SourceItem(BaseModel):
    """답변의 근거 1건. 프론트가 출처 카드를 그릴 때 쓰는 단위."""

    # 답변 본문의 [1], [2] 마커와 1:1로 대응하는 번호 (1부터 시작).
    # build_context()가 프롬프트에 붙인 [출처 n]과 같은 번호여야 한다.
    # 같은 리스트를 같은 순서로 enumerate해서 만들면 어긋나지 않는다.
    # 사이에 정렬이나 필터를 끼우면 LLM이 인용한 [2]와 화면의 [2]가 서로 다른 청크가 된다.
    index: int

    # OpenSearch 문서 ID (예: "af1ccb67:45"). 원본 청크까지 추적하는 키라서, 사용자 화면엔 안 보여도 로그/디버깅용으로 필요하다.
    doc_id: str

    # 어느 회사의 근거인지 (예: "cik:0001046179").회사명은 여기 넣지 않았다. 이름은 Neo4j가 SSOT라서 표시 단계에서 매핑
    entity_id: str

    # 공시 내 섹션명. 사용자에게 "어디서 나온 정보인지" 보여주는 용도.
    section_title: str

    # 청크 원문. 출처 카드에서 펼쳐 볼 때 쓴다. 원문 전체를 내려보내는 건 지금은 단순해서 택한 것이다.
    # 트래픽이 커지면 앞부분만 자르거나 doc_id로 지연 조회하는 방식을 검토한다.
    content: str

    # 검색 관련도. UI에서 "얼마나 관련 있었나" 참고용으로만 쓴다.LLM 프롬프트에는 넣지 않는다 (관련도와 신뢰도를 LLM이 혼동할 수 있어서).
    # min_max 정규화가 후보군 안에서 상대 점수를 만들기 때문에다른 질문의 점수와 비교하는 값이 아니다.
    score: float


class SourcesEvent(BaseModel):
    """근거 목록 이벤트. 스트림에서 가장 먼저 1번만 나간다."""

    # 이벤트 종류를 구분하는 태그. C3에서 SSE의 "event:" 줄에 그대로 쓴다.
    # 오타를 타입 체크가 잡아주고, 나중에 JSON을 다시 파싱할 때 이 값만 보고 어느 클래스인지 판별할 수 있어서다.
    event: Literal["sources"] = "sources"

    # 근거를 토큰보다 먼저 보내는 이유는, 프론트가 출처 카드를 먼저 그려두면 뒤이어 나오는 [1] 마커를
    # 즉시 카드와 연결할 수 있기 때문이다. 사용자에게도 "무엇을 근거로 답하는지"가 먼저 보인다.
    sources: list[SourceItem]


class TokenEvent(BaseModel):
    """LLM이 생성한 토큰(텍스트 조각) 1개. 답변이 끝날 때까지 여러 번 나간다."""

    event: Literal["token"] = "token"

    # 토큰 하나 또는 몇 글자 단위의 조각 (예: "안", "녕"). 완성된 문장이 아니므로, 합쳐서 보여주는 건 받는 쪽(프론트) 책임이다.
    text: str


class DoneEvent(BaseModel):
    """스트림 종료 신호. 마지막에 1번만 나간다."""

    # 이 이벤트가 있어야 프론트가 "정상 종료"와 "중간에 연결이 끊긴 것"을 구분한다.
    # 필드는 지금 없다. 토큰 사용량이나 finish_reason이 필요해지면 여기에 추가한다.
    # 에러용 이벤트(ErrorEvent)는 일부러 안 만들었다.
    # 생성 함수는 예외를 삼키지 않고 위로 올리고, 에러를 이벤트로 바꾸는 건 C3 책임이다.
    event: Literal["done"] = "done"


# 생성 함수의 반환 타입에 쓰는 합집합 타입.
# AsyncGenerator[AnswerEvent, None]으로 선언하면
# "sources → token 여러 개 → done" 셋 중 하나만 나온다는 걸 타입으로 보장한다.
# 이벤트를 받는 쪽은 event 필드 또는 isinstance로 분기한다.
AnswerEvent = SourcesEvent | TokenEvent | DoneEvent
