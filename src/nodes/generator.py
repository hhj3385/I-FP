"""
STEP 5: Generator Node
- 검색된 문서 + 회사 프로파일 + 질문 유형 + 이전 피드백을 종합하여 초안 생성
- 현재: EXAONE 로컬 (Claude API 잔액 충전 후 use_claude=True로 전환)
"""
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from src.state import IFPState

# Claude API 잔액 충전 후 True로 변경
USE_CLAUDE = False

_PROFILE_PATH = Path(__file__).parent.parent.parent / "data" / "company_profile.md"
_COMPANY_PROFILE: str | None = None


def _load_profile() -> str:
    global _COMPANY_PROFILE
    if _COMPANY_PROFILE is None:
        if _PROFILE_PATH.exists():
            _COMPANY_PROFILE = _PROFILE_PATH.read_text(encoding="utf-8")
        else:
            _COMPANY_PROFILE = ""
    return _COMPANY_PROFILE


_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 ㈜데이터누리의 공공사업 제안 전문가 AI, I&FP(Intelligence & Fast Proposal)입니다.

## 페르소나
- 역할: 데이터·AI·공공정보화 분야 제안 전략가
- 전문성: 나라장터 공고 분석, 제안서 초안 작성, 레퍼런스 기반 역량 매칭
- 원칙: 제공된 문서에 근거하여 답변하고, 특정 사실을 인용할 때 [문서 N] 형식으로 출처 표기

## 답변 규칙
1. 반드시 제공된 [참고 문서]와 회사 프로파일에 근거하여 작성합니다.
2. 특정 사실·수치·사례를 언급할 때 해당 [문서 번호]를 본문에 표기합니다 (예: [문서 1]).
3. 문서에 없는 내용은 지어내지 않으며, 불확실한 내용은 "확인 필요"로 표시합니다.
4. 질문 유형에 맞는 형식으로 작성합니다 (분석 보고서 / 제안서 초안 / 역량 매칭표 등).
5. 이전 피드백이 있으면 반드시 반영합니다.
6. 회사 강점(국내 유일 조달청 3자단가, NIA 핵심 파트너, 공공 레퍼런스 80건+)을 적극 활용합니다.

[㈜데이터누리 회사 프로파일]
{company_profile}"""),
    ("human", """[질문 유형] {question_type}
[질문] {formalized_question}

[참고 문서]
{context}

{feedback_section}

위 내용을 바탕으로 답변하세요. 사실을 인용할 때 [문서 N] 형식으로 출처를 표기해 주세요."""),
])


def _build_context(summary_docs: list, detail_docs: list) -> str:
    """문서에 전역 인덱스를 부여하여 LLM이 [문서 N]으로 인용할 수 있게 구성"""
    parts = []
    idx = 1
    if summary_docs:
        parts.append("## 개요 문서")
        for d in summary_docs[:3]:
            src = (d.get("metadata") or {}).get("source", "")
            label = f"[문서 {idx}]" + (f" ({src})" if src else "")
            parts.append(f"{label}\n{d['content'][:600]}")
            idx += 1
    if detail_docs:
        parts.append("## 세부 문서")
        for d in detail_docs[:5]:
            src = (d.get("metadata") or {}).get("source", "")
            label = f"[문서 {idx}]" + (f" ({src})" if src else "")
            parts.append(f"{label}\n{d['content'][:300]}")
            idx += 1
    return "\n\n".join(parts)


def _get_llm():
    if USE_CLAUDE:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.claude_model,
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=4096,
        )
    return ChatOllama(model=settings.exaone_model, temperature=0.3)


def generator_node(state: IFPState) -> IFPState:
    chain = _PROMPT | _get_llm()

    feedback = state.get("review_feedback")
    feedback_section = (
        f"[이전 리뷰 피드백 - 반드시 반영]\n{feedback}"
        if feedback else ""
    )

    context = _build_context(
        state.get("summary_docs") or [],
        state.get("detail_docs") or [],
    )

    result = chain.invoke({
        "question_type": state["question_type"],
        "formalized_question": state["formalized_question"],
        "context": context,
        "feedback_section": feedback_section,
        "company_profile": _load_profile(),
    })

    return {
        **state,
        "draft_answer": result.content,
    }
