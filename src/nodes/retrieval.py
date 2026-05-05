"""
STEP 4: Retrieval Node
- Planner 계획에 따라 요약/세부 리트리버 실행
- 문서 존재 여부만 판단 (OOD는 formalizer에서 차단)
"""
from src.retrievers.chroma_retriever import get_summary_retriever, get_detail_retriever
from src.state import IFPState


def retrieval_node(state: IFPState) -> IFPState:
    plan = state["retrieval_plan"]
    filters = plan.get("filters") or None
    queries = state["search_queries"]
    primary_query = state["formalized_question"]

    summary_docs, detail_docs = [], []

    if plan["use_summary"]:
        retriever = get_summary_retriever(filters)
        for q in queries:
            summary_docs.extend(retriever.invoke(q))
        # 중복 제거
        seen = set()
        summary_docs = [
            d for d in summary_docs
            if d.page_content not in seen and not seen.add(d.page_content)
        ]

    if plan["use_detail"]:
        retriever = get_detail_retriever(filters)
        for q in queries:
            detail_docs.extend(retriever.invoke(q))
        seen = set()
        detail_docs = [
            d for d in detail_docs
            if d.page_content not in seen and not seen.add(d.page_content)
        ]

    has_relevant = bool(summary_docs or detail_docs)

    summary_dicts = [{"content": d.page_content, "metadata": d.metadata} for d in summary_docs]
    detail_dicts  = [{"content": d.page_content, "metadata": d.metadata} for d in detail_docs]

    return {
        **state,
        "summary_docs": summary_dicts,
        "detail_docs": detail_dicts,
        "has_relevant_docs": has_relevant,
        "sources": _extract_sources(summary_dicts + detail_dicts),
    }


def _extract_sources(docs: list[dict]) -> list[dict]:
    """검색 문서에서 출처 목록을 중복 없이 추출 (최대 10건)"""
    seen: dict[str, dict] = {}
    for d in docs:
        meta = d.get("metadata") or {}
        name = (meta.get("source") or "").strip()
        if not name or name in seen:
            continue
        seen[name] = {
            "filename": name,
            "source_type": meta.get("source_type", "document"),
            "chunk_type": meta.get("chunk_type", ""),
        }
        if len(seen) >= 10:
            break
    return [{"index": i + 1, **v} for i, v in enumerate(seen.values())]
