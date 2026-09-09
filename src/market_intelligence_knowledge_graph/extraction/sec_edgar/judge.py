from langchain_openai import ChatOpenAI

from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import (
    ParagraphMention,
    SupplyJudgement,
    JudgedRelation,
    RelationData,
    EvidenceData,
)
from langchain_core.prompts import ChatPromptTemplate

_SYSTEM_PROMPT = """
너는 SEC 10-K 문서에서 기업 간 제조/공급 위탁 관계를 판정하는 애널리스트다.
주어진 문단이 실제로 "문서 주체 회사가 특정 대상 회사에 제조·조립·테스트 등을 위탁한다"는
관계를 서술하는지 판단하라. 단순 언급, 경쟁사 얘기 등은 관계 서술이 아니다.
process_type을 판단할 수 없으면 문자열 "none"이 아니라 null을 반환하라.
"""

# LangChain을 사용해 gpt-4o-mini 모델이 답변을 생성할 때, 앞서 정의한 SupplyJudgment Pydantic 클래스 구조에 딱 맞춰 응답하도록 설정

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(SupplyJudgement)

_prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM_PROMPT), ("human", "분석할 문단:\n{text}")]
)

_chain = _prompt | _llm


# 공시 문서(또는 추출된 텍스트 단락)를 LLM으로 분석하여, 두 기업 간의 공급망 관계(Edge/Relation)를 검증하고 Neo4j그래프 DB에 저장할 관계 객체(JudgedRelation)로 변환하는 핵심 판별(Judgement) 함수
def judge_paragraph(paragraph: ParagraphMention, to_ticker: str, to_entity_id: str) -> JudgedRelation | None:
    """
    paragraph: get_company_mentions()가 반환한 ParagraphMention 하나
    to_ticker: 위탁 대상 회사 티커. 예: "TSM" — 사람이 읽는 로그용
    to_entity_id: 위탁 대상 회사의 entity_id. 예: "cik:0001046179" — 그래프 MATCH용
    """

    # 체인 실행(llm 호출)
    supply: SupplyJudgement = _chain.invoke(input={"text": paragraph.text})

    if supply.confidence not in ("disclosed", "stated"):
        return None

    # LLM이 프롬프트 지침을 무시하고 문자열 "none"을 반환하는 경우가 실제로 관찰됨(프롬프트만으로는 100% 강제가 안 되므로 코드 레벨에서 방어)
    process_type = supply.process_type
    if process_type is not None and process_type.lower() == "none":
        return None

    return JudgedRelation(
        from_ticker=paragraph.from_ticker,
        to_ticker=to_ticker,
        from_entity_id="",
        to_entity_id=to_entity_id,
        evidence=EvidenceData(
            accession=paragraph.accession,
            form=paragraph.form,
            file_date=paragraph.file_date,
            matched_alias=paragraph.matched_alias,
            quoted_text=paragraph.text,
            reasoning=supply.reasoning,
        ),
        relation=RelationData(
            confidence=supply.confidence,
            dependency_pct=supply.dependency_pct,
            process_type=supply.process_type,
            as_of_date=paragraph.file_date,
        ),
    )
