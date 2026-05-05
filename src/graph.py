"""
LangGraph 메인 그래프
흐름: formalizer → planner → retrieval → (OOD 분기) → generator → review → (루프/통과) → final
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from src.state import IFPState
from src.nodes.formalizer import formalizer_node
from src.nodes.planner import planner_node
from src.nodes.retrieval import retrieval_node
from src.nodes.generator import generator_node
from src.nodes.review import review_node
from src.nodes.final import final_node
from config.settings import settings


def _route_after_formalizer(state: IFPState) -> str:
    """ood / greeting → final 직행 (planner·retrieval·generator·review 건너뜀)"""
    if state.get("is_early_ood"):
        return "final"
    return "planner"


def _route_after_retrieval(state: IFPState) -> str:
    """관련 문서가 없으면 바로 final(OOD)로"""
    if not state.get("has_relevant_docs"):
        return "final"
    return "generator"


def _route_after_review(state: IFPState) -> str:
    """리뷰 통과 시 final, 실패 시 max_iterations 체크 후 재생성 or final"""
    if state.get("review_passed"):
        return "final"
    if state.get("iteration_count", 0) >= settings.max_iterations:
        # 최대 루프 도달 → 현재 draft를 final로 넘김
        return "final"
    return "generator"


def build_graph(checkpointer=None):
    builder = StateGraph(IFPState)

    builder.add_node("formalizer", formalizer_node)
    builder.add_node("planner", planner_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("generator", generator_node)
    builder.add_node("review", review_node)
    builder.add_node("final", final_node)

    builder.set_entry_point("formalizer")

    builder.add_conditional_edges(
        "formalizer",
        _route_after_formalizer,
        {"planner": "planner", "final": "final"},
    )
    builder.add_edge("planner", "retrieval")
    builder.add_conditional_edges(
        "retrieval",
        _route_after_retrieval,
        {"generator": "generator", "final": "final"},
    )
    builder.add_edge("generator", "review")
    builder.add_conditional_edges(
        "review",
        _route_after_review,
        {"generator": "generator", "final": "final"},
    )
    builder.add_edge("final", END)

    return builder.compile(checkpointer=checkpointer)


def get_graph():
    """체크포인터 포함 그래프 (파이프라인 중단/재개 지원)"""
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "data" / "ifp_checkpoint.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer=checkpointer)
