from market_intelligence_knowledge_graph.rag.data_processing.extraction.filing_chunker import chunk_section
from market_intelligence_knowledge_graph.rag.data_processing.extraction.filing_text_loader import get_filing_sections
from market_intelligence_knowledge_graph.rag.data_processing.load.load_filing_chunks_index import (
    build_chunk_documents,
    bulk_index_documents,
)
from market_intelligence_knowledge_graph.rag.data_processing.opensearch_index.filing_chunks_mapping import (
    create_filing_chunks_index,
)
from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_chunk_document import FilingChunkDocument
from market_intelligence_knowledge_graph.rag.data_processing.schema.filing_section import FilingSection


def main():
    # 1. 인덱스 준비
    create_filing_chunks_index()

    # 2. Mongo DB filing_text(공시 본문) 조회
    filing_sections: list[FilingSection] = get_filing_sections()
    print(f"조회된 문서 수: {len(filing_sections)}")

    documents: list[FilingChunkDocument] = []
    # 3. 청크 및 임베딩
    for filing_section in filing_sections:
        chunks = chunk_section(section=filing_section)
        # print(
        #     f"{filing_section.entity_id} / {filing_section.section_id} → 청크 {len(chunks)}개, 원문 길이 {len(filing_section.text)}자"
        # )
        docs: list[FilingChunkDocument] = build_chunk_documents(filing_section=filing_section, chunks=chunks)
        documents.extend(docs)

    print(f"생성된 청크 문서 수: {len(documents)}")

    # 4. bulk 적재
    bulk_index_documents(documents=documents)


if __name__ == "__main__":
    main()
