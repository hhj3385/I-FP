"""
STEP 7: Final Node
- OOD 조기 판정(formalizer) / 문서 없음(retrieval) / 정상 답변 분기 처리
- OOD·인사 시 I&FP 페르소나 메시지 + 클릭 가능 추천 질문 반환
"""
from src.state import IFPState

_SUGGESTIONS = [
    "우리 회사의 과거 빅데이터 플랫폼 구축 사례를 알려줘",
    "AI 학습용 데이터 구축 사업 경험을 정리해줘",
    "공공데이터 개방 사업 수행 실적을 알려줘",
    "제안서 작성 시 강조할 우리 회사의 핵심 역량은?",
    "2025년 수행한 사업 목록을 정리해줘",
]

_GREETING_ANSWER = """\
안녕하세요! 저는 **㈜데이터누리**를 위해 만들어진 사내 AI 어시스턴트 **I&FP (Intelligence & Fast Proposal)**입니다.

철저하게 아카이빙된 사내 데이터만을 기반으로 과거 사업실적 조회, 역량 분석, 제안서 초안 작성을 도와드립니다.

이런 질문으로 대화를 시작해보심이 어떠신가요?\
"""

_OOD_ANSWER = """\
저는 **㈜데이터누리**를 위해 만들어진 사내 AI 어시스턴트 **I&FP**이며, 철저하게 아카이빙된 사내 데이터만을 기반으로 답변할 것을 원칙으로 하고 있습니다.

해당 질문보다는 이런 질문으로 대화를 시작해보심이 어떠신가요?\
"""


def final_node(state: IFPState) -> IFPState:
    sources = state.get("sources") or []
    qtype = (state.get("question_type") or "").lower()

    # ── 인사 (formalizer 조기 판정 or 키워드 감지)
    if qtype == "greeting" or state.get("is_early_ood") and qtype == "greeting":
        return {
            **state,
            "final_answer": _GREETING_ANSWER,
            "is_out_of_domain": False,
            "sources": [],
            "suggestions": _SUGGESTIONS,
        }

    # ── OOD (formalizer 조기 판정)
    if state.get("is_early_ood"):
        return {
            **state,
            "final_answer": _OOD_ANSWER,
            "is_out_of_domain": True,
            "sources": [],
            "suggestions": _SUGGESTIONS,
        }

    # ── 관련 문서 없음 (retrieval 이후 판정)
    if not state.get("has_relevant_docs"):
        return {
            **state,
            "final_answer": _OOD_ANSWER,
            "is_out_of_domain": True,
            "sources": [],
            "suggestions": _SUGGESTIONS,
        }

    # ── 정상 답변
    return {
        **state,
        "final_answer": state.get("draft_answer") or "(답변 생성 실패)",
        "is_out_of_domain": False,
        "sources": sources,
        "suggestions": None,
    }
