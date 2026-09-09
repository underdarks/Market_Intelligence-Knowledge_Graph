from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ParagraphMention, ProcessCapability, ProcessJudgement

_SYSTEM_PROMPT = """
너는 SEC 공시 문서(10-K, 20-F 등)에서 회사가 특정 공정/기술을 실제로 수행하는지 판정하는 애널리스트다.
주어진 문단이 회사가 이 공정을 실제로 제공·수행한다는 서술인지 판단하라.
상표권 목록 나열, 목차, 단순 명칭 언급(다른 맥락에서 스쳐 지나간 것)은 유효한 근거가 아니다.
"""


_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(schema=ProcessJudgement)

_prompt = ChatPromptTemplate(
    messages=[
        ("system", _SYSTEM_PROMPT),
        ("human", "공정/기술명: {process_name}\n\n문단:\n{text}"),
    ]
)

_chain = _prompt | _llm


# 문단 하나를 LLM에 태워 회사가 이 공정을 실제로 수행하는지 판정한다.
def judge_process_capability(
    paragraph: ParagraphMention, process_name: str, process_type: str
) -> ProcessCapability | None:
    if not all((paragraph, process_name, process_type)):
        return None

    process_judgement: ProcessJudgement = _chain.invoke(input={"process_name": process_name, "text": paragraph.text})

    if process_judgement.confidence not in ("disclosed", "stated"):
        return None

    return ProcessCapability(
        process_name=process_name,
        process_type=process_type,
        confidence=process_judgement.confidence,
        derived_from=paragraph.form,
        quoted_text=paragraph.text,
        accession=paragraph.accession,
        form=paragraph.form,
        file_date=paragraph.file_date,
    )
