"""
RFP 분석 전용 노드
- analyze_rfp_text()         : RFP 문서 구조 추출
- review_analysis()          : 분석 결과 품질 검토
- refine_analysis()          : 분석 개선
- match_rfp_capabilities()   : 역량 매칭 보고서 생성 (4차원 가중치 채점)
- review_match()             : 매칭 보고서 품질 검토
- refine_match()             : 매칭 보고서 개선
"""
import re
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings

_PROFILE_PATH = Path(__file__).parent.parent.parent / "data" / "company_profile.md"
_COMPANY_PROFILE: str | None = None


def _load_profile() -> str:
    global _COMPANY_PROFILE
    if _COMPANY_PROFILE is None:
        _COMPANY_PROFILE = (
            _PROFILE_PATH.read_text(encoding="utf-8")[:3000]
            if _PROFILE_PATH.exists() else ""
        )
    return _COMPANY_PROFILE


def _llm(temp: float = 0.1) -> ChatOllama:
    return ChatOllama(model=settings.exaone_model, temperature=temp)


# ── RFP 분석 프롬프트 ─────────────────────────────────────────────────────────

_ANALYZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 공공조달 RFP(제안요청서) 전문 분석가입니다.
제공된 문서에서 핵심 정보를 정확히 추출하여 아래 마크다운 구조로만 출력하세요.
확인되지 않는 항목은 "미확인"으로 표시합니다.

## 사업 개요
- **사업명**:
- **발주기관**:
- **사업예산**:
- **사업기간**:
- **사업목적**:

## 핵심 요구사항
-

## 기술 요구사항
-

## 참가 자격 요건
-

## 평가 기준
- 기술평가:
- 가격평가:

## 핵심 키워드
(쉼표 구분, 5~10개)"""),
    ("human", "다음 RFP 문서를 분석하세요:\n\n{rfp_text}"),
])

# ── 분석 검토 프롬프트 ────────────────────────────────────────────────────────

_REVIEW_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 RFP 분석 품질 검토 전문가입니다.
분석 결과를 검토하고 첫 줄에 반드시 ACCEPT 또는 REVISE를 출력합니다.

검토 기준:
1. 사업개요(사업명/발주기관/사업예산/사업기간/사업목적)가 모두 채워졌는가?
2. 핵심요구사항·기술요구사항·참가자격요건·평가기준이 구체적으로 작성되었는가?
3. 원문에서 확인 가능한데도 "미확인"으로 남긴 항목이 없는가?
4. 핵심 키워드가 5개 이상 추출되었는가?

출력 형식 (첫 줄만 판정, 이후 개선 항목 열거):
ACCEPT
또는:
REVISE
- 개선 항목 1
- 개선 항목 2"""),
    ("human", "[RFP 원문 (일부)]\n{rfp_text}\n\n[현재 분석 결과]\n{analysis}"),
])

# ── 분석 개선 프롬프트 ────────────────────────────────────────────────────────

_REFINE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 공공조달 RFP 전문 분석가입니다.
검토자의 피드백을 반영하여 분석 결과를 개선하세요.
기존 마크다운 섹션 구조를 유지하면서 지적된 항목만 수정합니다."""),
    ("human", "[RFP 원문 (일부)]\n{rfp_text}\n\n[현재 분석]\n{analysis}\n\n[검토 피드백]\n{critique}\n\n개선된 분석 결과를 출력하세요:"),
])

# ── 역량 매칭 프롬프트 (차원별 점수 → Python 가중합) ─────────────────────────

_MATCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 ㈜데이터누리의 공공사업 제안 전문가 AI, I&FP입니다.
RFP 요구사항과 우리 회사 역량을 비교하여 구체적인 매칭 보고서를 작성합니다.
수치·근거 없이 막연하게 쓰지 말고, 회사 프로파일과 과거 수행 사례를 직접 인용하세요.

[채점 원칙 — 반드시 준수]
• 확인된 직접 수행실적이 없으면 [B]점수는 40점 이하
• 간접 관련성만 있고 직접 기술 증거가 없으면 [A]점수는 65점 이하
• 90점 이상은 다수의 구체적·직접적 증거가 있을 때만 허용
• 관대화 금지: 평균적 역량 보유는 60~70점대

[㈜데이터누리 회사 프로파일]
{company_profile}"""),
    ("human", """[RFP 분석 요약]
{rfp_summary}

[관련 과거 수행 사례 (ChromaDB 검색 결과, {doc_count}건)]
{retrieved_docs}

---
아래 구조로 작성하세요. **차원별 점수 섹션을 반드시 먼저 출력**하세요.

## 차원별 점수
**[A] 기술·방법론 적합성**: XX점 — (RFP 요구 기술과 보유 역량 대조 한 줄)
**[B] 유사 수행실적**: XX점 — (검색된 유사 프로젝트 수·유사도, 없으면 40점 이하)
**[C] 참가자격 부합도**: XX점 — (면허·인증·기업규모 충족 여부 한 줄)
**[D] 평가기준 대응력**: XX점 — (제안서 평가항목 대응 가능성 한 줄)

## 매칭 강점
- (요구사항 항목별 부합 근거, 구체적 수행사례 인용)

## 보완 필요 사항
- (부족 항목과 대응 방안)

## 관련 레퍼런스
- (수행 사례 중 이 공고와 유사한 것, 없으면 "해당 사례 없음"으로 명시)

## 제안 전략
(접근 전략 2~3문단)"""),
])

# ── 매칭 검토 프롬프트 ────────────────────────────────────────────────────────

_REVIEW_MATCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 역량 매칭 보고서 품질 검토 전문가입니다.
첫 줄에 반드시 ACCEPT 또는 REVISE를 출력합니다.

검토 기준:
1. 차원별 점수([A]~[D])가 구체적 근거와 함께 제시되었는가?
2. 매칭 강점이 실제 수행사례를 직접 인용하는가?
3. 보완 필요사항에 구체적 대응방안이 있는가?
4. 제안 전략이 이 공고의 특성(예산·기간·발주처)을 반영하는가?
5. 점수가 근거 없이 지나치게 높게 부여되지 않았는가?

출력 형식:
ACCEPT
또는:
REVISE
- 개선 항목 1
- 개선 항목 2"""),
    ("human", "[RFP 분석 요약]\n{rfp_summary}\n\n[현재 매칭 보고서]\n{match_report}"),
])

# ── 매칭 개선 프롬프트 ────────────────────────────────────────────────────────

_REFINE_MATCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 ㈜데이터누리의 공공사업 제안 전문가 AI, I&FP입니다.
검토자의 피드백을 반영하여 역량 매칭 보고서를 개선합니다.
섹션 구조를 유지하면서 지적된 항목만 수정·보완합니다.
차원별 점수([A]~[D])가 변경될 경우 반드시 동일 형식을 유지합니다."""),
    ("human", "[현재 보고서]\n{match_report}\n\n[검토 피드백]\n{critique}\n\n[참고 수행 사례]\n{retrieved_docs}\n\n개선된 보고서를 출력하세요:"),
])


# ── 가중합 점수 산출 ──────────────────────────────────────────────────────────

_WEIGHTS = {"A": 0.35, "B": 0.30, "C": 0.20, "D": 0.15}

_GRADE_TABLE = [
    (90, "S", "탁월",   "#1b5e20"),
    (80, "A", "우수",   "#2e7d32"),
    (65, "B", "보통",   "#e65100"),
    (50, "C", "미흡",   "#b71c1c"),
    (0,  "D", "부적합", "#4a148c"),
]


def _parse_raw_scores(text: str) -> dict[str, int]:
    raw: dict[str, int] = {}
    for key in ("A", "B", "C", "D"):
        m = re.search(rf'\[{key}\][^\n]*?(\d{{1,3}})점', text)
        val = int(m.group(1)) if m else 60
        raw[key] = max(0, min(100, val))
    return raw


def _apply_doc_penalty(raw: dict[str, int], doc_count: int) -> dict[str, int]:
    if doc_count == 0:
        raw["B"] = min(raw["B"], 30)
    elif doc_count < 2:
        raw["B"] = min(raw["B"], 45)
    return raw


def _weighted_score(raw: dict[str, int]) -> tuple[int, str, str]:
    """(점수, 등급문자열, 색상코드)"""
    final = round(sum(raw[k] * _WEIGHTS[k] for k in _WEIGHTS))
    for threshold, g, label, color in _GRADE_TABLE:
        if final >= threshold:
            return final, f"{g} ({label})", color
    return final, "D (부적합)", "#4a148c"


def _build_score_header(score: int, grade: str, raw: dict[str, int]) -> str:
    return (
        f"## 종합 평가\n"
        f"**매칭 점수**: {score} / 100  \n"
        f"**등급**: {grade}  \n\n"
        f"| 평가 차원 | 가중치 | 점수 |\n"
        f"|-----------|--------|------|\n"
        f"| 기술·방법론 적합성 [A] | 35% | {raw['A']}점 |\n"
        f"| 유사 수행실적 [B]      | 30% | {raw['B']}점 |\n"
        f"| 참가자격 부합도 [C]    | 20% | {raw['C']}점 |\n"
        f"| 평가기준 대응력 [D]    | 15% | {raw['D']}점 |\n\n"
    )


def _assemble_report(raw_text: str, doc_count: int) -> tuple[str, int, str]:
    """LLM 출력 → (완성된 보고서, 점수, 색상)"""
    raw = _parse_raw_scores(raw_text)
    raw = _apply_doc_penalty(raw, doc_count)
    score, grade, color = _weighted_score(raw)
    header = _build_score_header(score, grade, raw)
    cleaned = re.sub(r'## 차원별 점수.*?(?=## )', '', raw_text, flags=re.DOTALL).strip()
    return header + cleaned, score, color


# ── 공개 API ──────────────────────────────────────────────────────────────────

def analyze_rfp_text(text: str) -> str:
    """RFP 텍스트 → 마크다운 구조 분석 결과"""
    chain = _ANALYZE_PROMPT | _llm(0.05)
    return chain.invoke({"rfp_text": text[:6000]}).content


def review_analysis(rfp_text: str, analysis: str) -> tuple[bool, str]:
    """(accepted, critique) — True면 검토 통과"""
    chain = _REVIEW_ANALYSIS_PROMPT | _llm(0.05)
    text = chain.invoke({"rfp_text": rfp_text[:2000], "analysis": analysis}).content.strip()
    if text.upper().startswith("ACCEPT"):
        return True, ""
    lines = [l for l in text.split("\n") if l.strip().startswith("-")]
    return False, "\n".join(lines) or "전반적 품질 미흡"


def refine_analysis(rfp_text: str, analysis: str, critique: str) -> str:
    """검토 피드백 반영 → 개선된 분석"""
    chain = _REFINE_ANALYSIS_PROMPT | _llm(0.1)
    return chain.invoke({"rfp_text": rfp_text[:2000], "analysis": analysis, "critique": critique}).content


def match_rfp_capabilities(rfp_summary: str, keywords: list[str]) -> tuple[str, list[dict], int, str]:
    """
    RFP 요약 + 키워드 → (매칭 보고서, 출처 목록, 점수, 색상)
    점수는 4차원 가중합으로 Python이 산출 (LLM 자유생성 아님)
    """
    from src.retrievers.chroma_retriever import get_summary_retriever, get_detail_retriever

    summary_ret = get_summary_retriever()
    detail_ret  = get_detail_retriever()

    raw_docs: list = []
    for kw in keywords[:4]:
        raw_docs.extend(summary_ret.invoke(kw))
        raw_docs.extend(detail_ret.invoke(kw))

    seen_src: set[str] = set()
    unique_docs: list = []
    for d in raw_docs:
        src = d.metadata.get("source", "")
        if src and src not in seen_src:
            seen_src.add(src)
            unique_docs.append(d)
        if len(unique_docs) >= 6:
            break

    context = "\n\n".join(
        f"[문서 {i+1}] ({d.metadata.get('source','')})\n{d.page_content[:400]}"
        for i, d in enumerate(unique_docs)
    )
    sources = [
        {"index": i+1, "filename": d.metadata.get("source",""), "chunk_type": d.metadata.get("chunk_type","")}
        for i, d in enumerate(unique_docs)
    ]

    chain = _MATCH_PROMPT | _llm(0.1)
    raw_text = chain.invoke({
        "rfp_summary": rfp_summary[:3000],
        "retrieved_docs": context,
        "company_profile": _load_profile(),
        "doc_count": len(unique_docs),
    }).content

    report, score, color = _assemble_report(raw_text, len(unique_docs))
    return report, sources, score, color


def review_match(rfp_summary: str, match_report: str) -> tuple[bool, str]:
    """(accepted, critique)"""
    chain = _REVIEW_MATCH_PROMPT | _llm(0.05)
    text = chain.invoke({"rfp_summary": rfp_summary[:1500], "match_report": match_report[:3000]}).content.strip()
    if text.upper().startswith("ACCEPT"):
        return True, ""
    lines = [l for l in text.split("\n") if l.strip().startswith("-")]
    return False, "\n".join(lines) or "구체성 부족"


def refine_match(match_report: str, critique: str, retrieved_docs: str, doc_count: int) -> tuple[str, int, str]:
    """개선된 (보고서, 점수, 색상)"""
    chain = _REFINE_MATCH_PROMPT | _llm(0.1)
    raw_text = chain.invoke({
        "match_report": match_report[:3000],
        "critique": critique,
        "retrieved_docs": retrieved_docs[:1000],
    }).content
    return _assemble_report(raw_text, doc_count)
