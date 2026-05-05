"""
STEP 4: Retrieval Node
- Planner 계획에 따라 요약/세부 리트리버 실행
- LLM 기반 관련성 검증 (엄격 모드)
"""
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.retrievers.chroma_retriever import get_summary_retriever, get_detail_retriever
from config.settings import settings
from src.state import IFPState

_RELEVANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 문서 관련성 판단기입니다.
아래 질문이 ㈜데이터누리(공공 IT·데이터 사업 회사)의 사내 문서로 답변 가능한지 판단하세요.

답변 가능한 질문: 회사 프로젝트·수주실적·제안서·역량·빅데이터·AI·공공 정보화
답변 불가 질문: 맛집·날씨·여행·스포츠·연예·일반상식·개인상담·요리·주식

검색된 문서 내용이 질문에 실제로 도움이 되면 true, 전혀 무관하면 false.
반드시 JSON만 출력하세요."""),
    ("human", """질문: {question}

검색된 문서 (상위 3개):
{doc_snippets}"""),
])


def _check_relevance(question: str, docs: list) -> bool:
    if not docs:
        return False
    llm = ChatOllama(model=settings.light_model, temperature=0, format="json")
    chain = _RELEVANCE_PROMPT | llm | JsonOutputParser()
    snippets = "\n---\n".join(d.page_content[:200] for d in docs[:3])
    try:
        result = chain.invoke({"question": question, "doc_snippets": snippets})
    except Exception:
        return True  # 판단 실패 시 generator에 위임
    val = result.get("is_relevant") if isinstance(result, dict) else None
    if val is None and isinstance(result, dict):
        val = result.get("relevant") or result.get("result")
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1", "관련", "있음")
    return bool(val) if val is not None else True


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

    all_docs = summary_docs + detail_docs
    has_relevant = _check_relevance(primary_query, all_docs) if all_docs else False

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
