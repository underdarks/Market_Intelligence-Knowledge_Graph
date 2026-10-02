from dotenv import load_dotenv

from market_intelligence_knowledge_graph.config.llm_gateway import close_llm_gateway_client
from market_intelligence_knowledge_graph.rag.generation.answer_generator import generate_answer
from market_intelligence_knowledge_graph.rag.schemas.answer_event import DoneEvent, SourcesEvent, TokenEvent
from market_intelligence_knowledge_graph.rag.search.search_filing import search_filing_chunks
import argparse
import asyncio

load_dotenv()


async def main(question: str, entity_id: str, lang_field: str, show_content) -> None:
    # search_filing_chunks는 동기 함수라 스레드로 넘겨서 이벤트 루프를 막지 않는다
    items = await asyncio.to_thread(search_filing_chunks, question, entity_id, lang_field)

    async for event in generate_answer(question, items):
        if isinstance(event, SourcesEvent):
            print(f"[sources] {len(event.sources)}건")
            for s in event.sources:
                print(f"  [{s.index}] {s.doc_id} / {s.section_title}")  # doc_id를 같이 찍어서 골든셋과 대조
                # if show_content:
                #     print(f"      {s.content}\n")
            print("\n[answer]")
        elif isinstance(event, TokenEvent):
            print(event.text, end="", flush=True)  # 토큰이 오는 대로 바로 출력
        elif isinstance(event, DoneEvent):
            print("\n[done]")

    await close_llm_gateway_client()  # 종료 시 커넥션 정리 (C3에서는 lifespan이 담당)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--entity-id", required=True)
    parser.add_argument("--lang-field", required=True, choices=["chunk_text_ko", "chunk_text_en"])
    parser.add_argument("--show-content", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        main(
            question=args.question,
            entity_id=args.entity_id,
            lang_field=args.lang_field,
            show_content=args.show_content,
        )
    )
