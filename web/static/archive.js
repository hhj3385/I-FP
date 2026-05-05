// ── 상태 ──────────────────────────────────────────────────────────────────────
let currentPage = 1;
let totalPages  = 1;
let searchTimer = null;
let _arcFiles   = [];  // 현재 페이지 파일 목록 (모달 클릭 시 인덱스로 참조)

const EXT_COLORS = {
  ".pdf":  "#e53935", ".pptx": "#f4511e", ".ppt": "#f4511e",
  ".xlsx": "#2e7d32", ".xls":  "#2e7d32", ".docx": "#1565c0",
  ".hwp":  "#00838f", ".hwpx": "#00838f",
  ".txt":  "#546e7a", ".md":   "#546e7a", ".zip":  "#6a1b9a",
};

function fmtSize(bytes) {
  if (bytes < 1024)        return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

// ── 통계 로드 ─────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const data = await fetch("/api/archive/stats").then(r => r.json());
    document.getElementById("statFiles").textContent   = data.file_count.toLocaleString();
    document.getElementById("statSummary").textContent = data.summary_chunks.toLocaleString();
    document.getElementById("statDetail").textContent  = data.detail_chunks.toLocaleString();
  } catch (e) {
    console.warn("stats load failed", e);
  }
}

// ── 파일 목록 로드 ────────────────────────────────────────────────────────────
async function loadFiles(page = 1) {
  currentPage = page;
  const q   = document.getElementById("searchQ").value.trim();
  const ext = document.getElementById("filterExt").value;

  const params = new URLSearchParams({ page, per_page: 50 });
  if (q)   params.set("q",   q);
  if (ext) params.set("ext", ext);

  const tbody = document.getElementById("fileTableBody");
  tbody.innerHTML = `<tr><td colspan="6" class="arc-table-empty">로딩 중...</td></tr>`;

  try {
    const data = await fetch("/api/archive/files?" + params).then(r => r.json());
    totalPages = data.pages;

    document.getElementById("arcTotalCount").textContent =
      `총 ${data.total.toLocaleString()}개`;

    if (!data.files.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="arc-table-empty">조건에 맞는 파일이 없습니다.</td></tr>`;
      renderPagination();
      return;
    }

    _arcFiles = data.files;
    tbody.innerHTML = data.files.map((f, i) => {
      const color   = EXT_COLORS[f.ext] || "#888";
      const indexed = f.indexed
        ? `<span class="arc-badge arc-badge--ok">인덱싱됨</span>`
        : `<span class="arc-badge arc-badge--no">미인덱싱</span>`;
      const dir = f.rel_path.includes("/")
        ? f.rel_path.substring(0, f.rel_path.lastIndexOf("/"))
        : "—";
      return `<tr class="arc-tr-clickable" onclick="openFileModal(${i})">
        <td class="arc-td-name" title="${escHtml(f.rel_path)}">${escHtml(f.name)}</td>
        <td><span class="arc-ext-badge" style="background:${color}20;color:${color}">${f.ext.replace(".", "").toUpperCase()}</span></td>
        <td class="arc-td-num">${fmtSize(f.size)}</td>
        <td class="arc-td-num">${f.modified}</td>
        <td class="arc-td-dir" title="${escHtml(f.rel_path)}">${escHtml(dir)}</td>
        <td>${indexed}</td>
      </tr>`;
    }).join("");

    renderPagination();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="arc-table-empty" style="color:#c62828">로드 실패: ${e.message}</td></tr>`;
  }
}

function renderPagination() {
  const pg = document.getElementById("pagination");
  if (totalPages <= 1) { pg.innerHTML = ""; return; }

  const pages = [];
  pages.push(`<button class="pg-btn" onclick="loadFiles(1)" ${currentPage===1?"disabled":""}>«</button>`);
  pages.push(`<button class="pg-btn" onclick="loadFiles(${currentPage-1})" ${currentPage===1?"disabled":""}>‹</button>`);

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  for (let i = start; i <= end; i++) {
    pages.push(`<button class="pg-btn ${i===currentPage?"pg-btn--active":""}" onclick="loadFiles(${i})">${i}</button>`);
  }

  pages.push(`<button class="pg-btn" onclick="loadFiles(${currentPage+1})" ${currentPage===totalPages?"disabled":""}>›</button>`);
  pages.push(`<button class="pg-btn" onclick="loadFiles(${totalPages})" ${currentPage===totalPages?"disabled":""}>»</button>`);
  pg.innerHTML = pages.join("");
}

function escHtml(s) {
  return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── 검색 이벤트 ───────────────────────────────────────────────────────────────
document.getElementById("searchQ").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadFiles(1), 350);
});
document.getElementById("filterExt").addEventListener("change", () => loadFiles(1));

// ── 업로드 ────────────────────────────────────────────────────────────────────
const uploadZone  = document.getElementById("uploadZone");
const uploadInner = document.getElementById("uploadInner");
const fileInput   = document.getElementById("fileInput");
const uploadQueue = document.getElementById("uploadQueue");

uploadInner.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFiles([...fileInput.files]);
  fileInput.value = "";
});

uploadZone.addEventListener("dragover", e => {
  e.preventDefault();
  uploadZone.classList.add("drag-over");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const files = [...e.dataTransfer.files];
  if (files.length) uploadFiles(files);
});

async function uploadFiles(files) {
  uploadQueue.style.display = "block";

  for (const file of files) {
    const itemId = "qi-" + Date.now() + Math.random().toString(36).slice(2);
    const item = document.createElement("div");
    item.className = "queue-item";
    item.id = itemId;
    item.innerHTML = `
      <span class="qi-name">${escHtml(file.name)}</span>
      <span class="qi-status qi-status--wait">대기 중</span>
      <span class="qi-msg"></span>`;
    uploadQueue.appendChild(item);

    await uploadSingleFile(file, itemId);
  }

  await loadStats();
  await loadFiles(currentPage);
}

async function uploadSingleFile(file, itemId) {
  const statusEl = document.querySelector(`#${itemId} .qi-status`);
  const msgEl    = document.querySelector(`#${itemId} .qi-msg`);

  statusEl.className = "qi-status qi-status--ing";
  statusEl.textContent = "업로드 중";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/archive/upload", { method: "POST", body: formData });

    if (!res.ok) {
      const err = await res.json();
      statusEl.className = "qi-status qi-status--err";
      statusEl.textContent = "오류";
      msgEl.textContent = err.error || "업로드 실패";
      return;
    }

    statusEl.textContent = "인덱싱 중";
    msgEl.textContent = "임베딩 생성 중...";

    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n\n");
      buf = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));

        if (data.type === "progress") {
          msgEl.textContent = data.message;
        } else if (data.type === "done") {
          if (data.success) {
            statusEl.className = "qi-status qi-status--ok";
            statusEl.textContent = "완료";
            msgEl.textContent = `${data.chars?.toLocaleString() || 0}자 추출`;
          } else {
            statusEl.className = "qi-status qi-status--err";
            statusEl.textContent = "실패";
            msgEl.textContent = data.error || "처리 실패";
          }
        } else if (data.type === "error") {
          statusEl.className = "qi-status qi-status--err";
          statusEl.textContent = "오류";
          msgEl.textContent = data.error || "알 수 없는 오류";
        }
      }
    }
  } catch (e) {
    statusEl.className = "qi-status qi-status--err";
    statusEl.textContent = "오류";
    msgEl.textContent = e.message;
  }
}

// ── 파일 상세 모달 ───────────────────────────────────────────────────────────
let _currentModalFile = null;

async function openFileModal(idx) {
  const f = _arcFiles[idx];
  if (!f) return;
  const name = f.name;
  _currentModalFile = name;
  document.getElementById("modalTitle").textContent = name;
  document.getElementById("modalSummary").textContent = "—";
  document.getElementById("modalDetail").textContent = "—";
  document.getElementById("modalPreview").textContent = "로딩 중...";
  document.getElementById("modalNotes").value = "";
  document.getElementById("modalMsg").textContent = "";
  document.getElementById("diagResults").innerHTML = "";
  document.getElementById("diagQuery").value = name.replace(/\.[^.]+$/, "");
  document.getElementById("diagSection").style.display = "none";
  document.getElementById("diagArrow").textContent = "▼";
  document.getElementById("fileModal").style.display = "flex";
  document.body.style.overflow = "hidden";

  try {
    const data = await fetch("/api/archive/file-detail?name=" + encodeURIComponent(name)).then(r => r.json());
    document.getElementById("modalSummary").textContent = (data.summary_chunks ?? 0).toLocaleString();
    document.getElementById("modalDetail").textContent = (data.detail_chunks ?? 0).toLocaleString();
    document.getElementById("modalPreview").textContent = data.preview || "(추출된 텍스트 없음)";
    document.getElementById("modalNotes").value = data.notes || "";
  } catch (e) {
    document.getElementById("modalPreview").textContent = "로드 실패: " + e.message;
  }
}

function closeModal() {
  document.getElementById("fileModal").style.display = "none";
  document.body.style.overflow = "";
  _currentModalFile = null;
}

function closeFileModal(e) {
  if (e.target === document.getElementById("fileModal")) closeModal();
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
});

async function saveNotes() {
  if (!_currentModalFile) return;
  const notes = document.getElementById("modalNotes").value;
  const btn = document.getElementById("modalSaveBtn");
  const msg = document.getElementById("modalMsg");

  btn.disabled = true;
  btn.textContent = "저장 중...";
  msg.textContent = "";

  try {
    const res = await fetch("/api/archive/file-notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: _currentModalFile, notes }),
    });
    const data = await res.json();
    if (data.success) {
      msg.textContent = notes.trim()
        ? `✓ 저장 완료 — ${data.indexed_chunks}개 청크 인덱싱됨`
        : "✓ 노트 삭제 완료";
      msg.style.color = "#2e7d32";
    } else {
      msg.textContent = "저장 실패: " + (data.error || "알 수 없는 오류");
      msg.style.color = "#c62828";
    }
  } catch (e) {
    msg.textContent = "오류: " + e.message;
    msg.style.color = "#c62828";
  } finally {
    btn.disabled = false;
    btn.textContent = "노트 저장 및 인덱싱";
  }
}

function toggleDiag() {
  const sec = document.getElementById("diagSection");
  const arrow = document.getElementById("diagArrow");
  const visible = sec.style.display !== "none";
  sec.style.display = visible ? "none" : "block";
  arrow.textContent = visible ? "▼" : "▲";
}

async function runDiag() {
  const q = document.getElementById("diagQuery").value.trim();
  if (!q) return;
  const resultsEl = document.getElementById("diagResults");
  resultsEl.innerHTML = "진단 중...";

  try {
    const data = await fetch("/api/archive/diagnose?q=" + encodeURIComponent(q)).then(r => r.json());
    if (!data.results || !data.results.length) {
      resultsEl.innerHTML = "(결과 없음)";
      return;
    }
    const THRESHOLD = 1.6;
    resultsEl.innerHTML = data.results.map(r => {
      if (r.error) return `<div class="diag-row diag-err">오류: ${escHtml(r.error)}</div>`;
      const ok = r.distance <= THRESHOLD;
      const cls = ok ? "diag-ok" : "diag-fail";
      const icon = ok ? "✓" : "✗";
      return `<div class="diag-row ${cls}">
        <span class="diag-icon">${icon}</span>
        <span class="diag-dist">${r.distance.toFixed(3)}</span>
        <span class="diag-src">${escHtml(r.source)}</span>
        <span class="diag-preview">${escHtml(r.preview.substring(0, 60))}…</span>
      </div>`;
    }).join("");
  } catch (e) {
    resultsEl.innerHTML = "오류: " + e.message;
  }
}

// ── 초기화 ────────────────────────────────────────────────────────────────────
loadStats();
loadFiles(1);
