"""
STEP 1: ChromaDB 기반 MMR 리트리버
- summary_retriever: 문서 전체 맥락 파악용 (요약 청크)
- detail_retriever:  세부 내용 검색용 (세부 청크)
"""
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.vectorstores import VectorStoreRetriever
from config.settings import settings


def _get_embedding():
    return OllamaEmbeddings(model=settings.exaone_model)


def _normalize_filter(filters: dict | None) -> dict | None:
    """ChromaDB는 다중 조건에 $and 연산자가 필요. 단일 조건은 그대로."""
    if not filters:
        return None
    if len(filters) == 1:
        return filters
    return {"$and": [{k: v} for k, v in filters.items()]}


def _build_search_kwargs(filters: dict | None) -> dict:
    kwargs = {
        "k": settings.mmr_k,
        "fetch_k": settings.mmr_fetch_k,
        "lambda_mult": settings.mmr_lambda,
    }
    f = _normalize_filter(filters)
    if f:
        kwargs["filter"] = f
    return kwargs


def get_summary_retriever(filters: dict | None = None) -> VectorStoreRetriever:
    db = Chroma(
        collection_name=settings.summary_collection,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=_get_embedding(),
    )
    return db.as_retriever(search_type="mmr", search_kwargs=_build_search_kwargs(filters))


def get_detail_retriever(filters: dict | None = None) -> VectorStoreRetriever:
    db = Chroma(
        collection_name=settings.detail_collection,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=_get_embedding(),
    )
    return db.as_retriever(search_type="mmr", search_kwargs=_build_search_kwargs(filters))


def get_docs_with_scores(
    query: str,
    collection: str,
    k: int = 5,
    filters: dict | None = None,
) -> list[tuple]:
    """similarity_search_with_score로 (Document, L2_distance) 쌍 반환."""
    db = Chroma(
        collection_name=collection,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=_get_embedding(),
    )
    kwargs: dict = {"k": k}
    f = _normalize_filter(filters)
    if f:
        kwargs["filter"] = f
    return db.similarity_search_with_score(query, **kwargs)
