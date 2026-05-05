from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class IFPState(TypedDict):
    # ── 입력
    raw_question: str                        # 사용자 원본 질문

    # ── STEP 2: Formalizer 결과
    question_type: Optional[str]             # rfp_analysis | proposal_draft | company_match | general
    formalized_question: Optional[str]       # 정제된 질문
    search_queries: Optional[list[str]]      # 검색에 사용할 쿼리 목록

    # ── STEP 3: Planner 결과
    retrieval_plan: Optional[dict[str, Any]] # {"use_summary": bool, "use_detail": bool, "filters": {...}}

    # ── STEP 4: Retrieval 결과
    summary_docs: Optional[list[dict]]       # 요약 청크 검색 결과
    detail_docs: Optional[list[dict]]        # 세부 청크 검색 결과
    has_relevant_docs: Optional[bool]        # 관련 문서 존재 여부

    # ── STEP 5: Generator 결과
    draft_answer: Optional[str]              # 생성된 초안

    # ── STEP 6: Review 결과
    review_passed: Optional[bool]
    review_feedback: Optional[str]           # 부족한 점 피드백
    counter_docs: Optional[list[dict]]       # 반론 검색 결과
    iteration_count: int                     # 루프 횟수 (최대 3회)

    # ── STEP 1: Formalizer OOD 조기 판정
    is_early_ood: Optional[bool]              # True면 planner/retrieval 건너뛰고 final로

    # ── STEP 7: Final 결과
    final_answer: Optional[str]
    is_out_of_domain: Optional[bool]
    sources: Optional[list[dict]]              # 답변에 사용된 출처 목록
    suggestions: Optional[list[str]]           # OOD/인사 시 클릭 가능 추천 질문

    # ── 공통: 대화 히스토리 (Human Gate용)
    messages: Annotated[list, add_messages]
