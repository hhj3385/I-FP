"""
STEP 6: Review Node (Reflexion 패턴)
- 생성된 답변의 반론 쿼리로 문서 재검색
- 모순/부족 여부 판단 → 피드백 저장 후 루프 or 통과
"""
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.retrievers.chroma_retriever import get_detail_retriever
from config.settings import settings
from src.state import IFPState


_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 엄격한 공공사업 제안 검토자입니다.
생성된 답변을 비판적으로 평가하고 아래 정확한 JSON만 반환하세요.

{{
  "passed": true/false,
  "feedback": "보완 필요 사항 (통과 시 빈 문자열)"
}}

평가 기준:
- 문서 근거 없이 주장하는 내용이 있는가?
- 논리적 모순이나 앞뒤가 안 맞는 부분이 있는가?
- 중요한 누락 사항이 있는가?

답변이 합리적이면 passed=true. 명확한 결함이 있을 때만 false."""),
    ("human", """[원래 질문] {question}

[생성된 답변]
{draft_answer}

[반론 검증용 문서]
{counter_docs}"""),
])

_COUNTER_QUERY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", '아래 답변에 대한 반론 검색 쿼리를 한 문장으로만 생성하세요. JSON: {{"counter_query": "..."}}'),
    ("human", "{draft_answer}"),
])


def _bool(val, default=False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1", "통과", "ok")
    return bool(val) if val is not None else default


def review_node(state: IFPState) -> IFPState:
    llm = ChatAnthropic(model=settings.claude_model, api_key=settings.anthropic_api_key, temperature=0)
    parser = JsonOutputParser()

    # 1단계: 반론 쿼리 생성
    try:
        pre_chain = _COUNTER_QUERY_PROMPT | llm | parser
        pre_result = pre_chain.invoke({"draft_answer": state["draft_answer"][:1000]})
        counter_query = pre_result.get("counter_query") or state["formalized_question"]
    except Exception:
        counter_query = state["formalized_question"]

    # 2단계: 반론 문서 검색
    try:
        retriever = get_detail_retriever()
        counter_docs = retriever.invoke(counter_query)
    except Exception:
        counter_docs = []
    counter_snippets = "\n---\n".join(d.page_content[:200] for d in counter_docs[:3])

    # 3단계: 최종 리뷰 판단
    try:
        review_chain = _REVIEW_PROMPT | llm | parser
        result = review_chain.invoke({
            "question": state["formalized_question"],
            "draft_answer": state["draft_answer"],
            "counter_docs": counter_snippets or "(반론 문서 없음)",
        })
    except Exception:
        result = {"passed": True, "feedback": ""}

    passed = _bool(result.get("passed"), default=True)
    feedback = result.get("feedback") or ""

    return {
        **state,
        "review_passed": passed,
        "review_feedback": feedback if not passed else None,
        "counter_docs": [{"content": d.page_content, "metadata": d.metadata} for d in counter_docs],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
