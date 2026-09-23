# 검색 결과를 LLM 프롬프트용 컨텍스트 문자열로 변환. 특정 모델에 최적화하지 않은 범용 텍스트 포맷.
from market_intelligence_knowledge_graph.rag.search.schema.retrieved_item import RetrievedItem


def build_context(items: list[RetrievedItem]) -> str:
    """
    검색 결과를 LLM 프롬프트에 넣을 번호 붙은 문자열로 변환.

    Returns:
        "[1] 청크1 내용\n\n[2] 청크2 내용\n\n..." 형태의 문자열
    """
    blocks = []
    for index, item in enumerate(items, start=1):
        block = (
            f"[출처 {index}]\n"  # s
            f"회사: {item.entity_id}\n"
            f"섹션: {item.section_title}\n"
            f"내용: {item.content}"
        )
        blocks.append(block)

    return "\n\n".join(blocks)
