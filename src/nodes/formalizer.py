"""
STEP 1: Formalizer Node
- 질문 유형 분류 (question_type): rfp_analysis | proposal_draft | company_match | general | ood | greeting
- ood / greeting → is_early_ood = True → planner/retrieval 건너뛰고 final로 직행
- 그 외 → 검색용 질문 정제 (formalized_question, search_queries)
"""
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config.settings import settings
from src.state import IFPState

# 명백한 인사/감사는 LLM 호출 없이 즉시 판정
_GREETING_KEYWORDS = {
    "안녕", "반가워", "반갑", "고마워", "감사", "수고", "잘 부탁",
    "hello", "hi", "bye", "thanks", "thank you",
}

# 명백히 도메인 외 키워드 → LLM 없이 즉시 OOD 처리
_OOD_KEYWORDS = {
    "맛집", "식당", "카페", "음식", "요리", "레시피",
    "날씨", "기온", "강수",
    "여행", "숙소", "호텔", "관광",
    "주식", "코인", "비트코인", "투자",
    "스포츠", "야구", "축구", "농구",
    "영화", "드라마", "연예인", "아이돌",
    "게임", "롤", "lol", "minecraft",
}

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 공공사업 제안 전문 AI 어시스턴트의 질문 분류기입니다.
사용자 질문을 분석하여 아래 정확한 JSON 형식으로만 응답하세요.

{{
  "question_type": "rfp_analysis | proposal_draft | company_match | general | ood | greeting 중 하나",
  "formalized_question": "검색에 최적화된 정제된 질문 (한 문장; ood·greeting이면 원문 그대로)",
  "search_queries": ["쿼리1", "쿼리2", "쿼리3"]
}}

question_type 분류 기준:
- rfp_analysis   : RFP/입찰 공고 문서 분석 요청
- proposal_draft : 제안서 작성·목차·섹션 생성 요청
- company_match  : 우리 회사 역량과 공고 매칭 요청
- general        : 우리 회사 사업실적·역량·아카이브 관련 질문
- ood            : 사내 데이터와 무관한 외부 지식(날씨·뉴스·수학·코딩 등) 또는 범위 외 질문
- greeting       : 인사, 감사, 칭찬, 잡담 등 업무 외 발화

반드시 위 3개 키를 모두 포함한 JSON만 출력하세요. 다른 텍스트는 절대 추가하지 마세요."""),
    ("human", "{raw_question}"),
])


def formalizer_node(state: IFPState) -> IFPState:
    raw_q = state["raw_question"]
    raw_lower = raw_q.lower().strip()

    # ── 명백한 OOD 키워드 판정 (LLM 호출 없이)
    if any(k in raw_lower for k in _OOD_KEYWORDS):
        return {
            **state,
            "question_type": "ood",
            "formalized_question": raw_q,
            "search_queries": [],
            "is_early_ood": True,
        }

    # ── 빠른 인사 판정 (LLM 호출 없이)
    if any(k in raw_lower for k in _GREETING_KEYWORDS) and len(raw_q) < 30:
        return {
            **state,
            "question_type": "greeting",
            "formalized_question": raw_q,
            "search_queries": [],
            "is_early_ood": True,
        }

    # ── LLM 분류
    llm = ChatOllama(model=settings.exaone_model, temperature=0, format="json")
    parser = JsonOutputParser()
    chain = _PROMPT | llm | parser

    try:
        result = chain.invoke({"raw_question": raw_q})
    except Exception:
        result = {}

    qtype = (
        result.get("question_type") or result.get("type") or "general"
    ).strip().lower()

    formalized = (
        result.get("formalized_question")
        or result.get("question")
        or result.get("formalized")
        or raw_q
    )
    queries = (
        result.get("search_queries")
        or result.get("queries")
        or result.get("search")
        or [formalized]
    )
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list) or not queries:
        queries = [formalized]

    is_early = qtype in ("ood", "greeting")

    return {
        **state,
        "question_type": qtype,
        "formalized_question": str(formalized),
        "search_queries": [str(q) for q in queries][:4],
        "is_early_ood": is_early,
    }
