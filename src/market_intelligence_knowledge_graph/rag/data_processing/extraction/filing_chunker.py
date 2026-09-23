from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_section import FilingSection

# 문장이 끝나는 지점으로 볼 문자들 (한국어/영어 공용)
_SENTENCE_ENDERS = (".", "!", "?", "\n")


def chunk_section(
    section: FilingSection,
    target_size: int = 1000,  # 목표 청크 크기 (800~1200 범위의 중간값)
    max_size: int = 1200,  # 문장 끝을 찾아 확장할 수 있는 최대 한도
    overlap_ratio: float = 0.12,  # 오버랩 12% (10~15% 범위 중간)
) -> list[dict]:
    """
    한 섹션의 원문을 문장 경계를 존중해서 800~1200자 안팎으로 분할.
    선택한 방식: "밀기"(문장을 다 채운 뒤 자름) — 문장이 잘리는 것보다 목표 크기를 약간 넘는 게 검색 품질에 덜 해롭다고 판단.
    """
    text = section.text
    n = len(text)

    # 섹션 자체가 짧으면 쪼갤 필요 없이 통째로 청크 1개
    if n <= max_size:
        return [{"text": text.strip(), "chunk_index": 0}]

    chunks: list[dict] = []
    cursor = 0
    chunk_index = 0

    while cursor < n:
        # 1. 일단 target_size만큼 앞으로 이동한 지점을 잠정 경계로 잡음
        tentative_end = min(cursor + target_size, n)

        # 2. tentative_end부터 max_size까지 범위에서 가장 가까운 문장 종결 부호를 탐색
        #    찾으면 그 문장 끝(부호 다음 위치)까지 "밀어서" 경계 확장
        boundary = tentative_end
        search_limit = min(cursor + max_size, n)
        for i in range(tentative_end, search_limit):
            if text[i] in _SENTENCE_ENDERS:
                boundary = i + 1
                break
        # for-else 없이 못 찾으면 boundary는 tentative_end 그대로 (문장부호가 안 보이면 그냥 자름)

        chunk_text = text[cursor:boundary].strip()
        if chunk_text:  # 공백만 남는 경우 방지
            chunks.append({"text": chunk_text, "chunk_index": chunk_index})
            chunk_index += 1

        if boundary >= n:  # 텍스트 끝에 도달하면 종료
            break

        # 3. 다음 시작 위치 = 이번 청크 길이의 overlap_ratio만큼 뒤로 물러난 지점
        chunk_len = boundary - cursor
        cursor = boundary - int(chunk_len * overlap_ratio)

    return chunks
