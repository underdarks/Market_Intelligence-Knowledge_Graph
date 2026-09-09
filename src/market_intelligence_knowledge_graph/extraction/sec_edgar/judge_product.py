from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from market_intelligence_knowledge_graph.extraction.sec_edgar.schemas import ProductJudgement

_SYSTEM_PROMPT = """
너는 SEC 10-K의 Business 섹션에서 회사가 설계·판매하는 제품/사업 라인을 추출하는 애널리스트다.

1. 회사가 실제로 설계하거나 판매하는 제품/사업만 추출하라. 시장 규모 설명, 경쟁사 언급,
   전략적 포부(마케팅성 표현)는 제외하라.
2. 최상위 제품 카테고리만 추출하라, 세부 파생 제품(예: 특정 GPU 시리즈)은 상위 카테고리로 묶어라"
   - 상위 카테고리와 그 하위 세부 항목이 함께 언급되면(예: "CPUs" 안에 "Desktop CPUs",
     "Notebook CPUs"가 포함되는 경우), 하위 항목은 제외하고 상위 카테고리 하나만 추출하라.
   - 한 회사에서 나올 제품 목록은 보통 5~10개를 넘지 않아야 한다. 그보다 많다면
     너무 세분화된 것이니 다시 상위 개념으로 통합하라.
3. 각 제품에 대해 회사의 역할이 설계(designs)인지 판매(sells)인지 둘 다(both)인지 판단하라.
4. 각 제품마다 그 판단의 근거가 된 원문 문장을 quoted_text에 그대로 인용하라.
   (원문을 요약하거나 바꿔 쓰지 말고 그대로 가져올 것 — 나중에 출처 검증에 쓰임)
"""

# temperature(온도)는 AI가 답변을 생성할 때 '창의성'과 '무작위성(랜덤성)'을 조절하는 매개변수(Parameter)
# 온도가 높으면 답변이 다양해지고, 낮추면 차분하고 일관됨(보통 0~2 설정)
#   - temperature = 0 (질문하신 코드의 설정) ➔ "극도의 엄격함과 일관성"
#   - temperature = 0.7 ~ 1.0 (기본값 수준) ➔ "자연스러운 대화"
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(ProductJudgement)

_prompt = ChatPromptTemplate.from_messages(
    messages=[
        ("system", _SYSTEM_PROMPT),
        ("human", "Business 섹션 원문:\n{text}"),
    ]
)

"""
LangChain(랭체인)의 핵심 기능인 LCEL(LangChain Expression Language)로, 데이터가 흐르는 방향을 파이프라인(|) 기호로 표현한 것
_1. prompt (1단계): 사용자가 입력한 값(변수)을 받아서, AI가 이해할 수 있는 완성된 프롬프트 문장(템플릿)을 만듭니다.
 2. |(데이터 넘겨줌): 만들어진 문장을 다음 단계로 넘겨줍니다.
 3. 넘겨받은 문장을 읽고 AI 모델이 최종 답변을 생성합니다.
"""
_chain = _prompt | _llm


def judge_products(ticker: str, business_section: str, filling_date: str) -> ProductJudgement:
    if not business_section:
        return ProductJudgement(products=[])

    product_judgement: ProductJudgement = _chain.invoke(input={"text": business_section})

    for product in product_judgement.products:
        product.as_of_date = filling_date

    return product_judgement
