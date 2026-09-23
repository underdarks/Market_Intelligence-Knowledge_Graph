from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from market_intelligence_knowledge_graph.config.opensearch_db import get_opensearch
from market_intelligence_knowledge_graph.rag.data_processing.load.filing_chunk_embedder import (
    embed_texts,
    get_language_field,
)
from market_intelligence_knowledge_graph.rag.data_processing.opensearch_index.filing_chunks_mapping import (
    INDEX_NAME,
)
from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_chunk_document import FilingChunkDocument
from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_section import FilingSection
import hashlib


# entity_id+section_id만으론 DART에서 유일성이 깨져서 section_title까지 포함
def _make_doc_id(filing_section: FilingSection, chunk_index: int) -> str:
    key = f"{filing_section.entity_id}:{filing_section.section_id}:{filing_section.section_title}"
    section_hash = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"{section_hash}:{chunk_index}"


def build_chunk_documents(filing_section: FilingSection, chunks: list[dict]) -> list[FilingChunkDocument]:
    """
    한 섹션에서 나온 청크들에 메타데이터(entity_id/section_id 등)와 임베딩을 붙여서
    OpenSearch filing_chunks 인덱스에 넣을 최종 문서 형태로 조합.

    Args:
        filing_section: 청크의 출처가 된 섹션 원본 (entity_id, section_id, source 등 메타데이터 보유)
        chunks: chunk_section()이 반환한 청크 리스트, 각 원소는 {"text": str, "chunk_index": int} 형태
    """
    # 1. 필드 조회
    lang_field = get_language_field(section=filing_section)
    chunk_texts = [chunk["text"] for chunk in chunks]

    # 2. 임베딩
    embeds: list[float] = embed_texts(texts=chunk_texts)
    filing_chunk_documents: list[FilingChunkDocument] = []

    for chunk, embed in zip(chunks, embeds):
        chunk_text = chunk["text"]
        fcd = FilingChunkDocument(
            doc_id=_make_doc_id(filing_section, chunk["chunk_index"]),
            entity_id=filing_section.entity_id,
            section_id=filing_section.section_id,
            section_title=filing_section.section_title,
            chunk_text_ko=chunk_text if lang_field == "chunk_text_ko" else None,
            chunk_text_en=chunk_text if lang_field == "chunk_text_en" else None,
            embedding=embed,
        )

        filing_chunk_documents.append(fcd)

    # 3. 반환
    return filing_chunk_documents


# FilingChunkDocument 리스트를 OpenSearch filing_chunks 인덱스에 bulk로 적재.
def bulk_index_documents(documents: list[FilingChunkDocument]) -> None:
    client: OpenSearch = get_opensearch()

    # opensearch-py의 helpers.bulk가 기대하는 액션 형식으로 변환
    # (내부적으로 _bulk API용 NDJSON을 만들어서 보내줌 — 우리가 직접 문자열 조립 안 해도 됨)
    """
        OpenSearch REST API에 대량 전송(_bulk)을 직접 하려면 원래 NDJSON(Newline Delimited JSON)이라는 까다로운 문자열 규격으로 직접 조립해야 합니다.
        helpers.bulk를 사용하면 위와 같은 문자열 조립을 직접 할 필요 없이, 
        우리가 정의한 Python Dict 리스트(actions)만 만들어 넘겨주면 SDK가 알아서 고성능 NDJSON 변환 및 대량 전송을 처리해 줍니다.
    """
    actions = [
        {
            "_index": INDEX_NAME,  # 메타데이터: 어느 인덱스에 넣을지
            "_id": doc.doc_id,  # 메타데이터: 이 문서의 고유 id
            "_source": doc.model_dump(
                exclude={"doc_id"}
            ),  # 진짜 데이터: 이 안에 든 게 실제로 검색 대상이 되는 필드들(doc_id제외)
        }
        for doc in documents
    ]

    # helpers.bulk를 통해 OpenSearch에 대량 전송 및 색인 수행
    # raise_on_error=False: 일부 문서 색인 실패(매핑 오류 등)가 발생해도 전체 파이프라인이 멈추지(Exception) 않고 계속 진행하도록 설정
    success_count, errors = bulk(client=client, actions=actions, raise_on_error=False)

    print(f"인덱싱 성공: {success_count}건")
    if errors:
        print(f"인덱싱 실패: {len(errors)}건")
        for err in errors:
            print(err)  # 실패 원인(매핑 불일치 등)을 바로 확인하려고 에러 내용 그대로 출력
