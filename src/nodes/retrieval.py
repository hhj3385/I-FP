"""
STEP 4: Retrieval Node
- Planner 계획에 따라 요약/세부 리트리버 실행
- 임베딩 유사도 점수(L2 거리)로 관련성 판단 → LLM 의존 제거
"""
from src.retrievers.chroma_retriever import (
    get_summary_retriever,
    get_detail_retriever,
    get_docs_with_scores,
)
from config.settings import settings
from src.state import IFPState

# L2 거리 임계값: 값이 클수록 관련도 낮음
# 완전히 다른 도메인(맛집·날씨 등)은 1.3+ 이상으로 튐
_SCORE_THRESHOLD = 1.6


def _has_relevant_by_score(question: str, filters: dict | None = None) -> bool:
    """summary 컬렉션 top-3의 최소 L2 거리가 임계값 이하면 관련 문서 있음으로 판단."""
    try:
        results = get_docs_with_scores(
            question,
            settings.summary_collection,
            k=3,
            filters=filters,
        )
        if not results:
            return False
        min_dist = min(score for _, score in results)
        return min_dist <= _SCORE_THRESHOLD
    except Exception:
        return True  # 점수 조회 실패 시 다운스트림(generator)에 위임


def retrieval_node(state: IFPState) -> IFPState:
    plan = state["retrieval_plan"]
    filters = plan.get("filters") or None
    queries = state["search_queries"]
    primary_query = state["formalized_question"]

    # ── 점수 기반 조기 차단 ───────────────────────────────────────────────────────
    # MMR 전체 검색 전에 L2 거리로 관련 문서 존재 여부를 먼저 확인.
    # 도메인 외 질문(맛집·날씨 등)은 여기서 바로 final(OOD)로 라우팅됨.
    if not _has_relevant_by_score(primary_query, filters):
        return {
            **state,
            "summary_docs": [],
            "detail_docs": [],
            "has_relevant_docs": False,
            "sources": [],
        }

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
