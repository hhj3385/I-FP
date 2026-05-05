"""
G2B(나라장터) 입찰공고 자동 수집기

API 키 발급: https://www.data.go.kr → 나라장터 입찰공고정보 서비스 신청
발급 후 .env 에  G2B_API_KEY=발급키  추가

실행: python -m src.collectors.g2b_collector
"""
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from config.settings import settings

_BASE_URL = (
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
    "/getBidPblancListInfoServc"
)
_SEEN_FILE = Path(settings.announcements_dir) / "seen.json"


# ── 중복 추적 ────────────────────────────────────────────────────────────────

def _load_seen() -> set[str]:
    _SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _SEEN_FILE.exists():
        return set(json.loads(_SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def _save_seen(seen: set[str]):
    _SEEN_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8"
    )


# ── API 호출 ─────────────────────────────────────────────────────────────────

def _fetch_page(start_dt: str, end_dt: str, page: int, rows: int = 100) -> dict:
    """API 호출 후 XML 파싱 → {'items': [...], 'totalCount': int} 반환"""
    params = {
        "serviceKey": settings.g2b_api_key,
        "numOfRows":  str(rows),
        "pageNo":     str(page),
        "inqryBgnDt": start_dt,   # YYYYMMDDHHMM
        "inqryEndDt": end_dt,     # YYYYMMDDHHMM
        "inqryDiv":   "1",        # 1=공고일 기준 (필수)
    }
    url = _BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()

    root = ET.fromstring(raw.decode("utf-8"))
    result_code = root.findtext(".//resultCode") or ""
    if result_code != "00":
        result_msg = root.findtext(".//resultMsg") or ""
        raise RuntimeError(f"G2B API 오류 [{result_code}]: {result_msg}")

    total = int(root.findtext(".//totalCount") or 0)
    items = [
        {child.tag: (child.text or "") for child in item_el}
        for item_el in root.findall(".//item")
    ]
    return {"items": items, "totalCount": total, "numOfRows": rows}


def _is_relevant(item: dict) -> bool:
    """키워드 매칭 + 최소 금액 필터"""
    name = (item.get("bidNtceNm") or "").lower()
    budget_raw = item.get("presmptPrce") or item.get("asignBdgtAmt") or "0"
    try:
        budget = float(str(budget_raw).replace(",", ""))
    except ValueError:
        budget = 0

    if budget < settings.g2b_min_budget:
        return False
    return any(kw in name for kw in settings.g2b_keywords)


def _item_to_text(item: dict) -> str:
    return "\n".join([
        f"[공고명] {item.get('bidNtceNm', '')}",
        f"[공고번호] {item.get('bidNtceNo', '')}-{item.get('bidNtceOrd', '')}",
        f"[공고기관] {item.get('ntceInsttNm', '')}",
        f"[수요기관] {item.get('dminsttNm', '')}",
        f"[공고일] {item.get('bidNtceDt', '')}",
        f"[마감일] {item.get('bidClseDt', '')}",
        f"[개찰일] {item.get('opengDt', '')}",
        f"[추정가격] {item.get('presmptPrce', '')} 원",
        f"[URL] {item.get('bidNtceUrl', '')}",
    ])


# ── 메인 수집 ────────────────────────────────────────────────────────────────

def collect(days_back: int | None = None) -> list[dict]:
    """
    최근 days_back 일의 관련 공고를 수집하여 반환.
    이미 수집된 공고(seen.json)는 제외.
    """
    if not settings.g2b_api_key:
        raise ValueError(
            "G2B API 키가 없습니다.\n"
            ".env 파일에  G2B_API_KEY=발급키  를 추가하세요.\n"
            "발급: https://www.data.go.kr → 나라장터 입찰공고정보 서비스"
        )

    days = days_back or settings.g2b_collect_days
    end   = datetime.now()
    start = end - timedelta(days=days)
    start_dt = start.strftime("%Y%m%d") + "0000"
    end_dt   = end.strftime("%Y%m%d")   + "2359"

    print(f"[G2B] 수집 기간: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")

    seen = _load_seen()
    new_items: list[dict] = []
    page = 1

    while True:
        try:
            data = _fetch_page(start_dt, end_dt, page)
        except Exception as e:
            print(f"  [ERROR] 페이지 {page} 호출 실패: {e}")
            break

        items = data.get("items") or []
        if not items:
            break

        for item in items:
            uid = f"{item.get('bidNtceNo','')}-{item.get('bidNtceOrd','')}"
            if uid in seen:
                continue
            if not _is_relevant(item):
                continue

            item["_uid"]       = uid
            item["_text"]      = _item_to_text(item)
            item["_collected"] = datetime.now().isoformat()
            new_items.append(item)
            seen.add(uid)

        total = data.get("totalCount", 0)
        rows  = data.get("numOfRows", 100)
        if page * rows >= total:
            break

        page += 1
        time.sleep(0.3)   # API 요청 간격

    print(f"[G2B] 신규 공고 {len(new_items)}건 수집")
    _save_seen(seen)
    return new_items


# ── 저장 ─────────────────────────────────────────────────────────────────────

def save_announcements(items: list[dict]) -> Path | None:
    """수집 결과를 날짜별 JSON 파일로 저장"""
    if not items:
        return None
    out_dir = Path(settings.announcements_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    fname.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[G2B] 저장: {fname}")
    return fname


# ── ChromaDB 적재 ─────────────────────────────────────────────────────────────

def ingest_to_chroma(items: list[dict]):
    """수집 공고를 ChromaDB detail 컬렉션에 즉시 적재"""
    if not items:
        return

    import chromadb
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_ollama import OllamaEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    embedding = OllamaEmbeddings(model=settings.exaone_model)
    client    = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    store     = Chroma(
        client=client,
        collection_name=settings.detail_collection,
        embedding_function=embedding,
    )

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    docs: list[Document] = []

    for item in items:
        meta = {
            "source":        item.get("bidNtceNm", "")[:100],
            "source_type":   "announcement",
            "bid_no":        item.get("_uid", ""),
            "org":           item.get("ntceInsttNm", ""),
            "close_date":    item.get("bidClseDt", ""),
            "budget":        str(item.get("presmptPrce", "")),
            "has_data":      True,
            "has_si":        True,
            "has_rfp":       True,
            "has_consulting": False,
            "has_security":  False,
            "chunk_type":    "detail",
        }
        for chunk in splitter.split_documents(
            [Document(page_content=item["_text"], metadata=meta)]
        ):
            docs.append(chunk)

    for i in range(0, len(docs), 5000):
        store.add_documents(docs[i:i+5000])

    print(f"[G2B] ChromaDB 적재 완료: {len(docs)}청크")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    days = int(sys.argv[1]) if len(sys.argv) > 1 else None

    items = collect(days)
    if items:
        save_announcements(items)
        print("\n적재 시작...")
        ingest_to_chroma(items)
    else:
        print("신규 공고 없음.")
