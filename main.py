"""
실행 진입점
사용법: python main.py
"""
import sys
import uuid
from src.graph import get_graph
from src.state import IFPState


def run(question: str):
    graph = get_graph()
    thread_id = str(uuid.uuid4())

    initial_state: IFPState = {
        "raw_question": question,
        "question_type": None,
        "formalized_question": None,
        "search_queries": None,
        "retrieval_plan": None,
        "summary_docs": None,
        "detail_docs": None,
        "has_relevant_docs": None,
        "draft_answer": None,
        "review_passed": None,
        "review_feedback": None,
        "counter_docs": None,
        "iteration_count": 0,
        "final_answer": None,
        "is_out_of_domain": None,
        "messages": [],
    }

    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n[질문] {question}\n{'='*60}")
    for step, event in enumerate(graph.stream(initial_state, config=config), 1):
        node_name = list(event.keys())[0]
        print(f"[{step}] {node_name} ✓")

    final_state = graph.get_state(config).values
    print(f"\n{'='*60}\n[최종 답변]\n{final_state.get('final_answer', '답변 없음')}")
    return final_state


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "우리 회사가 지원할 수 있는 SI 사업 공고를 분석해줘"
    run(q)
