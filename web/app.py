"""
I&FP Web Interface (FastAPI + Vanilla JS)
실행: python -m web.app
접속: http://localhost:8000
"""
import sys
import uuid
import asyncio
import json as _json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.graph import get_graph
from config.settings import settings

app = FastAPI(title="I&FP")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

# 그래프 단일 인스턴스
_graph = None
def graph():
    global _graph
    if _graph is None:
        _graph = get_graph()
    return _graph


class QueryRequest(BaseModel):
    question: str
    thread_id: str | None = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.post("/api/query")
async def query(req: QueryRequest):
    """전체 파이프라인 실행 후 최종 답변만 반환 (간단 버전)"""
    thread_id = req.thread_id or str(uuid.uuid4())
    initial_state = {
        "raw_question": req.question,
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

    def run():
        g = graph()
        steps = []
        for event in g.stream(initial_state, config=config):
            for node_name in event.keys():
                steps.append(node_name)
        final = g.get_state(config).values
        return {
            "thread_id": thread_id,
            "answer": final.get("final_answer") or "(답변 생성 실패)",
            "question_type": final.get("question_type"),
            "is_out_of_domain": final.get("is_out_of_domain", False),
            "iteration_count": final.get("iteration_count", 0),
            "sources": final.get("sources") or [],
            "steps": steps,
        }

    result = await asyncio.to_thread(run)
    return JSONResponse(result)


@app.post("/api/stream")
async def stream(req: QueryRequest):
    """SSE 방식으로 실시간 노드 진행상황 전송"""
    thread_id = req.thread_id or str(uuid.uuid4())
    initial_state = {
        "raw_question": req.question,
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
        "is_early_ood": None,
        "suggestions": None,
        "messages": [],
    }
    config = {"configurable": {"thread_id": thread_id}}

    async def event_gen():
        import json
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def producer():
            try:
                g = graph()
                for event in g.stream(initial_state, config=config):
                    for node_name, _ in event.items():
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            json.dumps({"type": "step", "node": node_name}, ensure_ascii=False),
                        )
                final = g.get_state(config).values
                payload = {
                    "type": "done",
                    "thread_id": thread_id,
                    "answer": final.get("final_answer") or "(답변 생성 실패)",
                    "question_type": final.get("question_type"),
                    "is_out_of_domain": final.get("is_out_of_domain", False),
                    "iteration_count": final.get("iteration_count", 0),
                    "sources": final.get("sources") or [],
                    "suggestions": final.get("suggestions") or [],
                }
                loop.call_soon_threadsafe(
                    queue.put_nowait, json.dumps(payload, ensure_ascii=False)
                )
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_event_loop().run_in_executor(None, producer)

        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class FeedbackRequest(BaseModel):
    thread_id: str | None = None
    question: str
    answer: str
    question_type: str | None = None
    rating: str
    feedback_text: str = ""


@app.post("/api/feedback")
async def save_feedback(req: FeedbackRequest):
    """좋아요/싫어요 피드백 저장 → data/feedback/feedback.jsonl"""
    import uuid
    from datetime import datetime, timezone

    feedback_dir = ROOT / "data" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    feedback_path = feedback_dir / "feedback.jsonl"

    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thread_id": req.thread_id,
        "question": req.question,
        "answer": req.answer,
        "question_type": req.question_type,
        "rating": req.rating,
        "feedback_text": req.feedback_text,
    }
    with feedback_path.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(record, ensure_ascii=False) + "\n")

    return JSONResponse({"success": True})


@app.get("/api/announcements")
async def get_announcements(
    q: str = "",
    org: str = "",
    date_from: str = "",
    date_to: str = "",
    min_budget: int = 0,
    max_budget: int = 0,
):
    """공고 목록 반환. q/org/date_from/date_to/min_budget/max_budget 으로 필터링 가능"""
    import json
    from pathlib import Path
    ann_dir = Path(__file__).parent.parent / "data" / "announcements"
    files = sorted(
        (f for f in ann_dir.glob("*.json") if f.name != "seen.json"),
        reverse=True,
    )

    all_items: list[dict] = []
    for f in files:
        try:
            all_items.extend(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass

    # ── 필터링 ────────────────────────────────────────────────
    q_lower   = q.strip().lower()
    org_lower = org.strip().lower()
    filtered: list[dict] = []
    for item in all_items:
        name      = (item.get("bidNtceNm")   or "").lower()
        ntce_org  = (item.get("ntceInsttNm") or "").lower()  # 공고기관
        dmin_org  = (item.get("dminsttNm")   or "").lower()  # 수요기관

        if q_lower and q_lower not in name and q_lower not in ntce_org and q_lower not in dmin_org:
            continue

        if org_lower and org_lower not in ntce_org and org_lower not in dmin_org:
            continue

        ntce_dt = (item.get("bidNtceDt") or "")[:10]   # YYYY-MM-DD
        if date_from and ntce_dt < date_from:
            continue
        if date_to and ntce_dt > date_to:
            continue

        try:
            budget = float(str(item.get("presmptPrce") or 0).replace(",", ""))
        except ValueError:
            budget = 0
        if min_budget and budget < min_budget:
            continue
        if max_budget and budget > max_budget:
            continue

        filtered.append(item)

    # 최신 100건 반환 (필터 없을 때는 50건)
    cap = 100 if (q_lower or date_from or date_to or min_budget or max_budget) else 50
    result = filtered[:cap]
    return JSONResponse({"count": len(result), "total": len(filtered), "items": result})


@app.post("/api/collect")
async def trigger_collect():
    """G2B 공고 수집 즉시 실행"""
    from config.settings import settings as cfg
    if not cfg.g2b_api_key:
        return JSONResponse(
            {"error": "G2B_API_KEY 미설정. .env에 추가 후 서버 재시작 필요."},
            status_code=400,
        )

    def run_collect():
        from src.collectors.g2b_collector import collect, save_announcements, ingest_to_chroma
        items = collect()
        if items:
            save_announcements(items)
            ingest_to_chroma(items)
        return len(items)

    count = await asyncio.to_thread(run_collect)
    return JSONResponse({"collected": count, "message": f"{count}건 수집 완료"})


ARCHIVE_TEMPLATE = Path(__file__).parent / "templates" / "archive.html"

_SUPPORTED_EXTS = {
    ".pdf", ".pptx", ".ppt", ".xlsx", ".xls",
    ".docx", ".hwpx", ".hwp", ".txt", ".md", ".zip",
}
_EXT_COLORS = {
    ".pdf": "red", ".pptx": "orange", ".ppt": "orange",
    ".xlsx": "green", ".xls": "green", ".docx": "blue",
    ".hwp": "teal", ".hwpx": "teal",
    ".txt": "gray", ".md": "gray", ".zip": "purple",
}


@app.get("/archive", response_class=HTMLResponse)
async def archive_page():
    return HTMLResponse(content=ARCHIVE_TEMPLATE.read_text(encoding="utf-8"))


@app.get("/api/archive/stats")
async def archive_stats():
    from config.settings import settings as cfg
    raw_dir = Path(cfg.raw_data_dir)
    file_count = sum(
        1 for p in raw_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTS
    )
    try:
        import chromadb as _chroma
        client = _chroma.PersistentClient(path=cfg.chroma_persist_dir)
        summary_n = client.get_collection(cfg.summary_collection).count()
        detail_n  = client.get_collection(cfg.detail_collection).count()
    except Exception:
        summary_n = detail_n = 0
    return JSONResponse({
        "file_count": file_count,
        "summary_chunks": summary_n,
        "detail_chunks": detail_n,
    })


@app.get("/api/archive/files")
async def list_archive_files(q: str = "", ext: str = "", page: int = 1, per_page: int = 50):
    from config.settings import settings as cfg
    from src.retrievers.ingest import load_checkpoint
    raw_dir = Path(cfg.raw_data_dir)
    indexed = load_checkpoint()

    q_lower  = q.strip().lower()
    ext_lower = ext.strip().lower()

    all_files = []
    for p in sorted(raw_dir.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _SUPPORTED_EXTS:
            continue
        if q_lower and q_lower not in p.name.lower():
            continue
        if ext_lower and p.suffix.lower() != ext_lower:
            continue
        stat = p.stat()
        all_files.append({
            "name":     p.name,
            "rel_path": str(p.relative_to(raw_dir)).replace("\\", "/"),
            "ext":      p.suffix.lower(),
            "size":     stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
            "indexed":  p.name in indexed,
        })

    total = len(all_files)
    start = (page - 1) * per_page
    page_files = all_files[start: start + per_page]
    return JSONResponse({
        "total": total,
        "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "files": page_files,
    })


@app.get("/api/archive/file-detail")
async def archive_file_detail(name: str = ""):
    """파일명으로 ChromaDB 청크 정보 + 보충 노트 반환."""
    if not name:
        return JSONResponse({"error": "name 파라미터 필요"}, status_code=400)
    from src.retrievers.ingest import get_file_chunks

    notes_path = Path(settings.raw_data_dir).parent / "file_notes.json"
    notes_data: dict = {}
    if notes_path.exists():
        try:
            notes_data = _json.loads(notes_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    chunks = await asyncio.to_thread(get_file_chunks, name)
    return JSONResponse({
        "name": name,
        **chunks,
        "notes": notes_data.get(name, ""),
    })


class FileNotesRequest(BaseModel):
    name: str
    notes: str


@app.post("/api/archive/file-notes")
async def save_file_notes(req: FileNotesRequest):
    """파일 보충 노트 저장 + ChromaDB 재인덱싱."""
    if not req.name:
        return JSONResponse({"error": "name 필요"}, status_code=400)

    notes_path = Path(settings.raw_data_dir).parent / "file_notes.json"
    notes_data: dict = {}
    if notes_path.exists():
        try:
            notes_data = _json.loads(notes_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if req.notes.strip():
        notes_data[req.name] = req.notes.strip()
    elif req.name in notes_data:
        del notes_data[req.name]

    notes_path.write_text(_json.dumps(notes_data, ensure_ascii=False, indent=2), encoding="utf-8")

    if req.notes.strip():
        from src.retrievers.ingest import ingest_note
        result = await asyncio.to_thread(ingest_note, req.name, req.notes.strip())
        return JSONResponse({"success": True, "indexed_chunks": result.get("chunks", 0)})
    return JSONResponse({"success": True, "indexed_chunks": 0})


@app.get("/api/archive/diagnose")
async def archive_diagnose(q: str = ""):
    """진단용: 쿼리에 대한 상위 문서 유사도 거리 반환."""
    if not q:
        return JSONResponse({"error": "q 파라미터 필요"}, status_code=400)
    from src.retrievers.ingest import get_similar_docs
    results = await asyncio.to_thread(get_similar_docs, q, 5)
    return JSONResponse({"query": q, "results": results})


@app.post("/api/archive/upload")
async def upload_archive_file(file: UploadFile = File(...)):
    """파일 업로드 → 저장 → ChromaDB 적재 (SSE 스트리밍)"""
    from config.settings import settings as cfg

    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_EXTS:
        return JSONResponse(
            {"error": f"지원하지 않는 형식: {ext}. 지원: {', '.join(sorted(_SUPPORTED_EXTS))}"},
            status_code=400,
        )

    upload_dir = Path(cfg.raw_data_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / file.filename
    content = await file.read()
    save_path.write_bytes(content)

    async def event_gen():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run_ingest():
            try:
                from src.retrievers.ingest import ingest_single_file
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    _json.dumps({"type": "progress", "message": "텍스트 추출 및 임베딩 중..."}, ensure_ascii=False),
                )
                result = ingest_single_file(save_path)
                loop.call_soon_threadsafe(queue.put_nowait, _json.dumps({**result, "type": "done"}, ensure_ascii=False))
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    _json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, run_ingest)

        yield f"data: {_json.dumps({'type': 'progress', 'message': f'{file.filename} 저장 완료, 인덱싱 시작...'}, ensure_ascii=False)}\n\n"
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


RFP_TEMPLATE = Path(__file__).parent / "templates" / "rfp.html"


class RFPMatchRequest(BaseModel):
    rfp_summary: str
    keywords: list[str]


@app.get("/rfp", response_class=HTMLResponse)
async def rfp_page():
    return HTMLResponse(content=RFP_TEMPLATE.read_text(encoding="utf-8"))


@app.post("/api/rfp/analyze")
async def rfp_analyze(file: UploadFile = File(...)):
    """RFP 파일 업로드 → 텍스트 추출 → LLM 분석 (SSE)"""
    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_EXTS:
        return JSONResponse({"error": f"지원하지 않는 형식: {ext}"}, status_code=400)

    upload_dir = Path(settings.raw_data_dir).parent / "rfp_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / file.filename
    save_path.write_bytes(await file.read())

    async def event_gen():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run():
            try:
                from src.retrievers.ingest import EXTRACTORS
                loop.call_soon_threadsafe(queue.put_nowait,
                    _json.dumps({"type": "step", "step": "extract", "message": "텍스트 추출 중..."}, ensure_ascii=False))

                extractor = EXTRACTORS.get(ext)
                if not extractor:
                    raise ValueError(f"추출기 없음: {ext}")
                text = extractor(save_path)
                if not text.strip():
                    raise ValueError("텍스트 내용을 추출할 수 없습니다 (이미지 전용 문서)")

                loop.call_soon_threadsafe(queue.put_nowait,
                    _json.dumps({"type": "step", "step": "analyze",
                                 "message": "RFP 분석 중... (30~60초 소요)"}, ensure_ascii=False))

                from src.rfp_graph import run_analyze_with_events
                for event in run_analyze_with_events(text):
                    if event["type"] == "done_analysis":
                        loop.call_soon_threadsafe(queue.put_nowait,
                            _json.dumps({"type": "done", "analysis": event["analysis"],
                                         "filename": file.filename, "chars": len(text)},
                                        ensure_ascii=False))
                    else:
                        loop.call_soon_threadsafe(queue.put_nowait,
                            _json.dumps(event, ensure_ascii=False))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait,
                    _json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, run)
        yield f"data: {_json.dumps({'type': 'step', 'step': 'save', 'message': f'{file.filename} 저장 완료'}, ensure_ascii=False)}\n\n"
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/rfp/match")
async def rfp_match(req: RFPMatchRequest):
    """RFP 분석 결과 기반 역량 매칭 (SSE)"""
    async def event_gen():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run():
            try:
                from src.rfp_graph import run_match_with_events
                for event in run_match_with_events(req.rfp_summary, req.keywords):
                    loop.call_soon_threadsafe(queue.put_nowait,
                        _json.dumps(event, ensure_ascii=False))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait,
                    _json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, run)
        yield f"data: {_json.dumps({'type': 'step', 'step': 'match', 'message': '관련 사례 검색 및 매칭 분석 시작...'}, ensure_ascii=False)}\n\n"
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
