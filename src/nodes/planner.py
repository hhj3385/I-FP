"""
STEP 3: Planner Node
- 어떤 리트리버를 쓸지, 어떤 메타데이터 필터를 적용할지 결정
"""
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config.settings import settings
from src.state import IFPState


_ALLOWED_FILTER_KEYS = {"has_si", "has_consulting", "has_security", "has_rfp", "has_data", "source"}


_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 문서 검색 전략 전문가입니다.
정제된 질문과 질문 유형을 보고, 최적의 검색 계획을 아래 정확한 JSON 형식으로만 반환하세요.

{{
  "use_summary": true/false,
  "use_detail": true/false,
  "filters": {{}}
}}

사용 가능한 메타데이터 필터 키:
- has_si (boolean): 시스템 구축 사업 여부
- has_consulting (boolean): 컨설팅 사업 여부
- has_security (boolean): 보안 사업 여부
- has_rfp (boolean): RFP/제안요청서 문서 여부
- has_data (boolean): 데이터/AI 사업 여부

기본 권장: 둘 다 true. 필터는 명확히 필요할 때만 추가하고, 필요 없으면 빈 객체.
반드시 위 3개 키를 포함한 JSON만 출력하세요."""),
    ("human", """질문 유형: {question_type}
정제된 질문: {formalized_question}"""),
])


def planner_node(state: IFPState) -> IFPState:
    llm = ChatAnthropic(model=settings.claude_model, api_key=settings.anthropic_api_key, temperature=0)
    parser = JsonOutputParser()
    chain = _PROMPT | llm | parser

    try:
        result = chain.invoke({
            "question_type": state["question_type"],
            "formalized_question": state["formalized_question"],
        })
    except Exception:
        result = {}

    use_summary = result.get("use_summary", True)
    use_detail = result.get("use_detail", True)
    filters = result.get("filters", {}) or {}

    # 허용된 키만 통과
    if isinstance(filters, dict):
        filters = {k: v for k, v in filters.items() if k in _ALLOWED_FILTER_KEYS}
    else:
        filters = {}

    return {
        **state,
        "retrieval_plan": {
            "use_summary": bool(use_summary),
            "use_detail": bool(use_detail),
            "filters": filters,
        },
    }
