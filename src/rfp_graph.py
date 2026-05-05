"""
RFP 분석·역량 매칭 LangGraph 피드백 루프
흐름:
  Analyze: rfp_analyze → rfp_review_analysis → (rfp_refine_analysis → rfp_review_analysis) × MAX_ITER → END
  Match:   rfp_match   → rfp_review_match    → (rfp_refine_match   → rfp_review_match)    × MAX_ITER → END
"""
from typing import TypedDict
from langgraph.graph import StateGraph, END
from config.settings import settings

MAX_ITER = 2


# ── 상태 정의 ─────────────────────────────────────────────────────────────────

class RFPAnalyzeState(TypedDict):
    rfp_text: str
    analysis: str
    critique: str
    iter: int


class RFPMatchState(TypedDict):
    rfp_summary: str
    keywords: list
    match_report: str
    critique: str
    iter: int
    sources: list
    score: int
    score_color: str
    retrieved_docs: str
    doc_count: int


# ── Analyze 노드 ──────────────────────────────────────────────────────────────

def _rfp_analyze(state: RFPAnalyzeState) -> dict:
    from src.nodes.rfp_analyzer import analyze_rfp_text
    return {"analysis": analyze_rfp_text(state["rfp_text"]), "iter": 0, "critique": ""}


def _rfp_review_analysis(state: RFPAnalyzeState) -> dict:
    from src.nodes.rfp_analyzer import review_analysis
    accepted, critique = review_analysis(state["rfp_text"], state["analysis"])
    return {"critique": "ACCEPT" if accepted else critique}


def _rfp_refine_analysis(state: RFPAnalyzeState) -> dict:
    from src.nodes.rfp_analyzer import refine_analysis
    improved = refine_analysis(state["rfp_text"], state["analysis"], state["critique"])
    return {"analysis": improved, "iter": state.get("iter", 0) + 1}


def _route_analysis(state: RFPAnalyzeState) -> str:
    if state.get("critique") == "ACCEPT" or state.get("iter", 0) >= MAX_ITER:
        return "end"
    return "refine"


# ── Match 노드 ────────────────────────────────────────────────────────────────

def _rfp_match(state: RFPMatchState) -> dict:
    from src.nodes.rfp_analyzer import match_rfp_capabilities
    report, sources, score, color = match_rfp_capabilities(
        state["rfp_summary"], state["keywords"]
    )
    return {
        "match_report": report, "sources": sources,
        "score": score, "score_color": color,
        "iter": 0, "critique": "",
        "doc_count": len(sources), "retrieved_docs": "",
    }


def _rfp_review_match(state: RFPMatchState) -> dict:
    from src.nodes.rfp_analyzer import review_match
    accepted, critique = review_match(state["rfp_summary"], state["match_report"])
    return {"critique": "ACCEPT" if accepted else critique}


def _rfp_refine_match(state: RFPMatchState) -> dict:
    from src.nodes.rfp_analyzer import refine_match
    report, score, color = refine_match(
        state["match_report"], state["critique"],
        state.get("retrieved_docs", ""), state.get("doc_count", 0)
    )
    return {"match_report": report, "score": score, "score_color": color,
            "iter": state.get("iter", 0) + 1}


def _route_match(state: RFPMatchState) -> str:
    if state.get("critique") == "ACCEPT" or state.get("iter", 0) >= MAX_ITER:
        return "end"
    return "refine"


# ── 그래프 빌더 ───────────────────────────────────────────────────────────────

def build_rfp_analyze_graph():
    builder = StateGraph(RFPAnalyzeState)

    builder.add_node("rfp_analyze",          _rfp_analyze)
    builder.add_node("rfp_review_analysis",  _rfp_review_analysis)
    builder.add_node("rfp_refine_analysis",  _rfp_refine_analysis)

    builder.set_entry_point("rfp_analyze")
    builder.add_edge("rfp_analyze", "rfp_review_analysis")
    builder.add_conditional_edges(
        "rfp_review_analysis", _route_analysis,
        {"end": END, "refine": "rfp_refine_analysis"},
    )
    builder.add_edge("rfp_refine_analysis", "rfp_review_analysis")

    return builder.compile()


def build_rfp_match_graph():
    builder = StateGraph(RFPMatchState)

    builder.add_node("rfp_match",        _rfp_match)
    builder.add_node("rfp_review_match", _rfp_review_match)
    builder.add_node("rfp_refine_match", _rfp_refine_match)

    builder.set_entry_point("rfp_match")
    builder.add_edge("rfp_match", "rfp_review_match")
    builder.add_conditional_edges(
        "rfp_review_match", _route_match,
        {"end": END, "refine": "rfp_refine_match"},
    )
    builder.add_edge("rfp_refine_match", "rfp_review_match")

    return builder.compile()


# ── SSE 이벤트 제너레이터 ─────────────────────────────────────────────────────
# graph.stream() 누적 방식 대신 노드 함수를 직접 순차 호출.
# LangGraph 버전별 스트림 포맷 차이로 인한 accumulated 미갱신 버그 방지.

def run_analyze_with_events(rfp_text: str):
    """Analyze Reflexion 루프 → SSE 이벤트 dict 순차 yield"""
    from src.nodes.rfp_analyzer import analyze_rfp_text, review_analysis, refine_analysis

    # 1. 초기 분석
    yield {"type": "step", "step": "analyze", "message": "RFP 분석 중... (30~60초 소요)"}
    analysis = analyze_rfp_text(rfp_text)
    yield {"type": "step", "step": "analyze", "message": "RFP 분석 완료 — 품질 검토 중..."}

    # 2. Reflexion 루프 (최대 MAX_ITER회)
    for i in range(MAX_ITER):
        accepted, critique = review_analysis(rfp_text, analysis)
        if accepted:
            yield {"type": "step", "step": "review", "message": "품질 검토 통과 ✓"}
            break
        yield {"type": "step", "step": "review",
               "message": f"개선 항목 발견 — 피드백 반영 중 ({i + 1}/{MAX_ITER})"}
        analysis = refine_analysis(rfp_text, analysis, critique)
        yield {"type": "step", "step": "refine",
               "message": f"분석 개선 완료 ({i + 1}/{MAX_ITER}회)"}

    yield {"type": "done_analysis", "analysis": analysis}


def run_match_with_events(rfp_summary: str, keywords: list):
    """Match Reflexion 루프 → SSE 이벤트 dict 순차 yield"""
    from src.nodes.rfp_analyzer import match_rfp_capabilities, review_match, refine_match

    # 1. 초기 매칭
    yield {"type": "step", "step": "match", "message": "역량 매칭 분석 중... (30~60초 소요)"}
    report, sources, score, color = match_rfp_capabilities(rfp_summary, keywords)
    doc_count = len(sources)
    yield {"type": "step", "step": "match", "message": "역량 매칭 완료 — 보고서 검토 중..."}

    # 2. Reflexion 루프 (최대 MAX_ITER회)
    for i in range(MAX_ITER):
        accepted, critique = review_match(rfp_summary, report)
        if accepted:
            yield {"type": "step", "step": "mreview", "message": "보고서 검토 통과 ✓"}
            break
        yield {"type": "step", "step": "mreview",
               "message": f"보고서 개선 중 ({i + 1}/{MAX_ITER})"}
        report, score, color = refine_match(report, critique, "", doc_count)
        yield {"type": "step", "step": "mrefine",
               "message": f"보고서 개선 완료 ({i + 1}/{MAX_ITER}회)"}

    yield {
        "type": "done",
        "report":      report,
        "sources":     sources,
        "score":       score,
        "score_color": color,
    }
