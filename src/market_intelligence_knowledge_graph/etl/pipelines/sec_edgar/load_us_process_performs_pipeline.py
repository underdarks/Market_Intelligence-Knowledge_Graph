import time

from edgar import Filing, set_identity

from market_intelligence_knowledge_graph.config import neo4j_db
from market_intelligence_knowledge_graph.config.config import SEC_IDENTITY, SEC_RATE_LIMIT_SLEEP
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.judge_process_capability import judge_process_capability
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.schemas import ParagraphMention, ProcessCapability
from market_intelligence_knowledge_graph.etl.extraction.sec_edgar.edgar_text_extraction import (
    get_filing_mentions,
    get_original_20F,
)
from market_intelligence_knowledge_graph.etl.load.graph.load_process_capability import load_process_performs
from market_intelligence_knowledge_graph.utils.utils import to_entity_id
from market_intelligence_knowledge_graph.sample.targets import MANUAL_PERFORMS_US

set_identity(SEC_IDENTITY)

# product, company-[:PERFORMS] -> product 관계 생성
def main():
    neo4j_db.verify()

    for target in MANUAL_PERFORMS_US:
        try:
            # 1. 20-F에서 회사가 특정 공정을 수행하는 데이터 추출
            ticker: str = target["ticker"]
            form: str = target["form"]
            keyword: str = target["keyword"]
            process_type: str = target["process_type"]
            entity_id: str = to_entity_id(ticker)
            original_20F: Filing | None = get_original_20F(ticker=ticker)

            paragraph_mentions: list[ParagraphMention] = get_filing_mentions(filing=original_20F, keyword=keyword)

            # 2. LLM에게 질의해서 실제 회사가 공정을 수행하는지 확인(상표권 목록처럼 그냥 단어만 스친 경우는 걸러내야 함)
            for paragraph in paragraph_mentions:
                process_capabilitiy: ProcessCapability | None = judge_process_capability(
                    paragraph=paragraph, process_name=keyword, process_type=process_type
                )
                if process_capabilitiy is None:
                    continue

                load_process_performs(
                    entity_id=entity_id,
                    process_capability=process_capabilitiy,
                )

        except Exception as e:
            print(f"[ERR] {e}")
        finally:
            time.sleep(SEC_RATE_LIMIT_SLEEP)


if __name__ == "__main__":
    try:
        main()
    finally:
        neo4j_db.close()
