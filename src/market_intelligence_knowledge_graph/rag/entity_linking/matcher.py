import re
from dataclasses import dataclass

from market_intelligence_knowledge_graph.rag.entity_linking.alias_index import AliasEntry, AliasIndex
from market_intelligence_knowledge_graph.rag.entity_linking.link_types import LinkResult, LinkStatus, LinkedEntity
from market_intelligence_knowledge_graph.rag.entity_linking.normalizer import normalize, squash


# 질문 안에서 별칭이 걸린 구간 1개 (matcher 내부용, 앞의 _는 모듈 밖에서 쓰지 말라는 관례)
@dataclass(frozen=True)
class _Span:

    start: int  # 시작 위치 (포함). 한글이면 squash 텍스트, 영문이면 normalize 텍스트 기준 좌표
    end: int  # 끝 위치 (미포함). 파이썬 슬라이스 규칙과 같음: text[start:end]
    entry: AliasEntry  # 어떤 별칭이 걸렸는지

    @property  # 메서드를 필드처럼 사용: span.length (괄호 없이)
    def length(self) -> int:
        return self.end - self.start


# 한글 별칭: squash된 질문에서 부분 문자열로 모든 출현 위치를 찾는다.
def _find_korean_spans(text: str, entries: tuple[AliasEntry, ...]) -> list[_Span]:
    spans: list[_Span] = []
    for entry in entries:
        if not entry.is_hangul:
            continue
        pos = text.find(entry.key)  # 없으면 -1
        while pos != -1:
            spans.append(_Span(start=pos, end=pos + len(entry.key), entry=entry))
            # 다음 탐색은 pos + 1부터: 겹치는 출현도 놓치지 않기 위함
            pos = text.find(entry.key, pos + 1)
    return spans


# 영문·숫자 별칭: 앞뒤가 영숫자가 아닐 때만 매칭한다 (단어 경계)
def _find_english_spans(text: str, entries: tuple[AliasEntry, ...]) -> list[_Span]:
    spans: list[_Span] = []
    for entry in entries:
        if entry.is_hangul:
            continue
        # (?<![a-z0-9]) : 바로 앞 글자가 영숫자면 안 됨 (부정 후방탐색)
        # (?![a-z0-9])  : 바로 뒤 글자가 영숫자면 안 됨 (부정 전방탐색)
        # \b를 안 쓰는 이유: 파이썬은 한글도 단어 문자로 봐서 "nvda실적"에서 매칭 실패함
        # re.escape: "S&P", "A.B" 같은 별칭의 특수문자를 정규식 문법이 아닌 글자로 취급
        pattern = rf"(?<![a-z0-9]){re.escape(entry.key)}(?![a-z0-9])"
        for m in re.finditer(pattern, text):  # 모든 매칭을 순서대로 순회
            spans.append(_Span(start=m.start(), end=m.end(), entry=entry))
    return spans


def _remove_overlaps(spans: list[_Span]) -> list[_Span]:
    """겹치는 구간 중 긴 별칭만 남긴다 (탐욕 알고리즘).

    예: "현대차증권"이 채택되면 그 안의 "현대차"는 버린다 (다른 회사로 잘못 세는 것 방지)
    같은 좌표계 안에서만 호출할 것: 한글끼리, 영문끼리 따로
    """
    # 정렬 키: 길이 내림차순(-length), 같은 길이면 앞쪽 먼저(start) -> 결과가 항상 같게
    ordered = sorted(spans, key=lambda s: (-s.length, s.start))
    kept: list[_Span] = []
    for span in ordered:
        # 두 구간이 안 겹치는 조건: 한쪽이 다른 쪽보다 완전히 앞에 끝남
        if all(span.end <= k.start or k.end <= span.start for k in kept):
            kept.append(span)
    return kept


def status_for_count(n: int) -> LinkStatus:
    """확정된 회사 수 -> 상태. AMBIGUOUS는 별도 판정이라 여기서 안 다룸."""
    if n == 0:
        return LinkStatus.NOT_FOUND
    if n == 1:
        return LinkStatus.CONFIRMED
    return LinkStatus.MULTIPLE


def match(index: AliasIndex, question: str) -> LinkResult:
    """질문(또는 LLM이 뽑은 surface)에서 회사를 찾아 회사 단위로 판정한다.
    이후엔 두 곳에서 재사용됨: surface 문자열 매칭, LLM 실패 시 질문 전체 폴백
    """
    # 1. 인덱스 key를 만들 때와 같은 함수로 질문을 정규화 (다른 함수 쓰면 매칭 자체가 안 됨)
    q_ko = squash(question)  # 한글 별칭용: 공백 제거
    q_en = normalize(question)  # 영문 별칭용: 공백 유지

    # 2. 좌표계별로 따로 찾고 따로 겹침 제거
    #    squash는 공백을 지워서 위치가 달라지므로, 한글 구간과 영문 구간을 섞어 비교하면 안 됨
    ko_spans = _remove_overlaps(_find_korean_spans(q_ko, index.entries))
    en_spans = _remove_overlaps(_find_english_spans(q_en, index.entries))

    # 3. 회사 단위로 합치기: 같은 회사 별칭이 여러 개 걸려도 1건
    #    긴 별칭부터 순회해서 회사당 첫 번째(=가장 긴 별칭)만 남김
    #    정렬 키에 alias를 넣은 이유: 길이가 같을 때도 실행마다 같은 결과가 나오게
    by_entity: dict[str, LinkedEntity] = {}  # entity_id -> 채택된 LinkedEntity
    for span in sorted(ko_spans + en_spans, key=lambda s: (-s.length, s.entry.alias)):
        entry = span.entry
        if entry.entity_id in by_entity:
            continue  # 이미 더 긴 별칭으로 채택된 회사
        by_entity[entry.entity_id] = LinkedEntity(
            entity_id=entry.entity_id,
            name=entry.name,  # 화면 표시용 정식명
            matched_alias=entry.alias,  # 질문에서 실제로 걸린 별칭 원문 (되묻기 문구에 사용)
        )

    # 4. entity_id로 정렬: dict 순서는 입력 순서라서, 테스트 비교가 흔들리지 않게 고정
    entities = tuple(sorted(by_entity.values(), key=lambda e: e.entity_id))

    # 5. 서로 다른 회사 수로 판정
    #    AMBIGUOUS는 여기서 안 나옴: 별칭 충돌 key는 인덱스에서 제외되므로 별칭 1개 = 회사 1개
    if not entities:
        status = LinkStatus.NOT_FOUND
    elif len(entities) == 1:
        status = LinkStatus.CONFIRMED
    else:
        status = LinkStatus.MULTIPLE

    return LinkResult(status=status, entities=entities)
