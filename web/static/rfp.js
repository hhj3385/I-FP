// ── 상태 ──────────────────────────────────────────────────────────────────────
let _analysisText = "";
let _keywords     = [];

// ── 유틸 ──────────────────────────────────────────────────────────────────────
function escHtml(s) {
  return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function renderMarkdown(md) {
  if (!md) return "";
  let h = md.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  h = h.replace(/^####\s+(.*)$/gm, "<h4>$1</h4>");
  h = h.replace(/^###\s+(.*)$/gm,  "<h3>$1</h3>");
  h = h.replace(/^##\s+(.*)$/gm,   "<h2>$1</h2>");
  h = h.replace(/^#\s+(.*)$/gm,    "<h1>$1</h1>");
  h = h.replace(/\*\*(.+?)\*\*/g,  "<strong>$1</strong>");
  h = h.replace(/\*(.+?)\*/g,      "<em>$1</em>");
  h = h.replace(/`(.+?)`/g,        "<code>$1</code>");
  // 테이블 렌더링
  h = h.replace(/^\|(.+)\|$/gm, (row) => {
    if (/^[\s|:-]+$/.test(row)) return "";
    const cells = row.split("|").slice(1,-1).map(c => `<td>${c.trim()}</td>`).join("");
    return `<tr>${cells}</tr>`;
  });
  h = h.replace(/(<tr>.*?<\/tr>\n?)+/gs, m => `<table class="rfp-md-table">${m}</table>`);
  h = h.replace(/^(\s*)-\s+(.*)$/gm, "$1• $2");
  h = h.split(/\n\n+/).map(p =>
    p.match(/^<(h[1-4]|table)/) ? p : "<p>" + p.replace(/\n/g,"<br>") + "</p>"
  ).join("\n");
  return h;
}

// ── 마크다운 섹션 파싱 ────────────────────────────────────────────────────────
function parseSections(markdown) {
  const result = {};
  const parts = markdown.split(/^## /m).filter(Boolean);
  for (const part of parts) {
    const nl = part.indexOf("\n");
    const title = nl > -1 ? part.slice(0, nl).trim() : part.trim();
    const body  = nl > -1 ? part.slice(nl + 1).trim() : "";
    result[title] = body;
  }
  return result;
}

function parseOverview(text) {
  const fields = {};
  for (const line of text.split("\n")) {
    const m = line.match(/\*\*(.+?)\*\*\s*[:：]\s*(.+)/);
    if (m) fields[m[1].trim()] = m[2].trim();
  }
  return fields;
}

function parseBullets(text) {
  return text.split("\n")
    .map(l => l.replace(/^[-•]\s+/, "").trim())
    .filter(Boolean);
}

function parseKeywords(text) {
  return text.split(/[,，、]/).map(k => k.trim()).filter(Boolean);
}

// ── 분석 결과 렌더링 ──────────────────────────────────────────────────────────
const SECTION_CONFIG = [
  { key: "핵심 요구사항",   icon: "🎯", color: "#4f6dff" },
  { key: "기술 요구사항",   icon: "⚙️", color: "#0288d1" },
  { key: "참가 자격 요건",  icon: "📋", color: "#2e7d32" },
  { key: "평가 기준",       icon: "📊", color: "#f57c00" },
];

function renderAnalysis(markdown) {
  const sections = parseSections(markdown);

  // ── 사업 개요 카드
  const overview = parseOverview(sections["사업 개요"] || "");
  const overviewGrid = document.getElementById("overviewGrid");
  const overviewItems = [
    { label: "사업명",   value: overview["사업명"]   || "—", wide: true },
    { label: "발주기관", value: overview["발주기관"] || "—" },
    { label: "사업예산", value: overview["사업예산"] || "—" },
    { label: "사업기간", value: overview["사업기간"] || "—" },
    { label: "사업목적", value: overview["사업목적"] || "—", wide: true },
  ];
  overviewGrid.innerHTML = overviewItems.map(item => `
    <div class="rfp-ov-item ${item.wide ? "rfp-ov-wide" : ""}">
      <span class="rfp-ov-label">${escHtml(item.label)}</span>
      <span class="rfp-ov-value">${escHtml(item.value)}</span>
    </div>`).join("");

  // ── 요구사항 카드
  const cardsGrid = document.getElementById("cardsGrid");
  cardsGrid.innerHTML = SECTION_CONFIG.map(({ key, icon, color }) => {
    const body = sections[key] || "";
    if (!body) return "";
    const bullets = parseBullets(body);
    const items = bullets.map(b =>
      `<li class="rfp-card-item"><span class="rfp-card-dot" style="background:${color}"></span>${escHtml(b)}</li>`
    ).join("");
    return `
      <div class="rfp-card">
        <div class="rfp-card-head" style="border-color:${color}20">
          <span class="rfp-card-icon">${icon}</span>
          <span class="rfp-card-title" style="color:${color}">${escHtml(key)}</span>
        </div>
        <ul class="rfp-card-list">${items || "<li class='rfp-card-empty'>해당 없음</li>"}</ul>
      </div>`;
  }).join("");

  // ── 핵심 키워드
  const kwRaw = sections["핵심 키워드"] || "";
  const kwList = parseKeywords(kwRaw);
  _keywords = kwList;

  const kwSection = document.getElementById("keywordsSection");
  const kwTags    = document.getElementById("kwTags");
  if (kwList.length) {
    kwTags.innerHTML = kwList.map(k =>
      `<span class="rfp-kw-tag">${escHtml(k)}</span>`
    ).join("");
    kwSection.style.display = "block";
  }
}

// ── 진행 단계 표시 (Analyze) ──────────────────────────────────────────────────
const STEP_MAP = {
  save:    "prog-save",
  extract: "prog-extract",
  analyze: "prog-analyze",
  review:  "prog-review",
  refine:  "prog-refine",
};

function setStep(stepId, status) {
  // 선택적 스텝(개선)은 active/done일 때만 표시
  if (stepId === "refine" && (status === "active" || status === "done")) {
    document.getElementById("prog-line-refine").classList.add("rfp-prog-line--visible");
    document.getElementById("prog-refine").classList.add("rfp-prog-step--visible");
  }
  const el = document.getElementById(STEP_MAP[stepId]);
  if (!el) return;
  el.className = el.className
    .replace(/rfp-prog-step--(wait|active|done)/g, "")
    .trim() + ` rfp-prog-step--${status}`;
}

// ── 진행 단계 표시 (Match) ────────────────────────────────────────────────────
const MATCH_STEP_MAP = {
  match:   "mprog-match",
  mreview: "mprog-review",
  mrefine: "mprog-refine",
};

function setMatchStep(stepId, status) {
  if (stepId === "mrefine" && (status === "active" || status === "done")) {
    document.getElementById("mprog-line-refine").classList.add("rfp-prog-line--visible");
    document.getElementById("mprog-refine").classList.add("rfp-prog-step--visible");
  }
  const el = document.getElementById(MATCH_STEP_MAP[stepId]);
  if (!el) return;
  el.className = el.className
    .replace(/rfp-prog-step--(wait|active|done)/g, "")
    .trim() + ` rfp-prog-step--${status}`;
}

// ── 업로드 & 분석 ─────────────────────────────────────────────────────────────
const uploadZone  = document.getElementById("uploadZone");
const uploadInner = document.getElementById("uploadInner");
const fileInput   = document.getElementById("rfpFileInput");

uploadInner.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) startAnalysis(fileInput.files[0]);
  fileInput.value = "";
});
uploadZone.addEventListener("dragover", e => { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) startAnalysis(e.dataTransfer.files[0]);
});

async function startAnalysis(file) {
  _analysisText = "";
  _keywords = [];
  document.getElementById("resultSection").style.display = "none";
  document.getElementById("matchSection").style.display  = "none";
  document.getElementById("progressMsg").textContent = "분석 준비 중...";

  // 스텝 초기화
  Object.keys(STEP_MAP).forEach(s => setStep(s, "wait"));
  // 선택적 스텝 숨기기
  document.getElementById("prog-line-refine").classList.remove("rfp-prog-line--visible");
  document.getElementById("prog-refine").classList.remove("rfp-prog-step--visible");

  document.getElementById("progressSection").style.display = "block";
  document.getElementById("progressSection").scrollIntoView({ behavior: "smooth" });

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/rfp/analyze", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      document.getElementById("progressMsg").textContent = `오류: ${err.error}`;
      return;
    }

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

        if (data.type === "step") {
          document.getElementById("progressMsg").textContent = data.message;
          const step = data.step;

          if (step === "save")    { setStep("save", "done"); }
          if (step === "extract") { setStep("save", "done"); setStep("extract", "active"); }
          if (step === "analyze") { setStep("extract", "done"); setStep("analyze", "active"); }
          if (step === "review")  { setStep("analyze", "done"); setStep("review", "active"); }
          if (step === "refine")  { setStep("review", "wait"); setStep("refine", "active"); }

        } else if (data.type === "done") {
          // 완료 — 활성화된 스텝만 done 처리
          ["save","extract","analyze","review","refine"].forEach(s => {
            const el = document.getElementById(STEP_MAP[s]);
            if (el && el.className.includes("active")) setStep(s, "done");
            else if (el && !el.className.includes("opt") || el?.className.includes("visible")) setStep(s, "done");
          });
          // 안전하게 전체 done
          setStep("save", "done"); setStep("extract", "done");
          setStep("analyze", "done"); setStep("review", "done");

          document.getElementById("progressMsg").textContent =
            `분석 완료 — ${data.filename} (${data.chars?.toLocaleString()}자 추출)`;

          _analysisText = data.analysis;
          document.getElementById("resultFilename").textContent = data.filename;

          const rs = document.getElementById("resultSection");
          rs.style.display = "block";
          renderAnalysis(data.analysis);
          rs.scrollIntoView({ behavior: "smooth" });

        } else if (data.type === "error") {
          document.getElementById("progressMsg").textContent = `오류: ${data.message}`;
          Object.keys(STEP_MAP).forEach(s => setStep(s, "wait"));
        }
      }
    }
  } catch (e) {
    document.getElementById("progressMsg").textContent = `네트워크 오류: ${e.message}`;
  }
}

// ── 역량 매칭 ─────────────────────────────────────────────────────────────────
document.getElementById("matchBtn").addEventListener("click", startMatch);

async function startMatch() {
  const matchSection = document.getElementById("matchSection");
  const matchProgress = document.getElementById("matchProgress");
  const matchBody     = document.getElementById("matchBody");
  const matchSources  = document.getElementById("matchSources");
  const matchProgMsg  = document.getElementById("matchProgMsg");

  matchSection.style.display  = "block";
  matchProgress.style.display = "block";
  matchBody.style.display     = "none";
  matchSources.style.display  = "none";

  // 매칭 스텝 초기화
  Object.keys(MATCH_STEP_MAP).forEach(s => setMatchStep(s, "wait"));
  document.getElementById("mprog-line-refine").classList.remove("rfp-prog-line--visible");
  document.getElementById("mprog-refine").classList.remove("rfp-prog-step--visible");

  matchProgMsg.textContent = "분석 중...";
  matchSection.scrollIntoView({ behavior: "smooth" });

  try {
    const res = await fetch("/api/rfp/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rfp_summary: _analysisText, keywords: _keywords }),
    });

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

        if (data.type === "step") {
          matchProgMsg.textContent = data.message;
          const step = data.step;

          if (step === "match")   { setMatchStep("match", "active"); }
          if (step === "mreview") { setMatchStep("match", "done"); setMatchStep("mreview", "active"); }
          if (step === "mrefine") { setMatchStep("mreview", "wait"); setMatchStep("mrefine", "active"); }

        } else if (data.type === "done") {
          setMatchStep("match", "done");
          setMatchStep("mreview", "done");

          matchProgress.style.display = "none";
          matchBody.style.display     = "block";
          matchBody.innerHTML = renderMarkdown(data.report);

          // 매칭 점수 배지 — Python 가중합 점수 사용
          if (data.score != null) {
            const score = data.score;
            const color = data.score_color || (
              score >= 90 ? "#1b5e20" :
              score >= 80 ? "#2e7d32" :
              score >= 65 ? "#e65100" :
              score >= 50 ? "#b71c1c" : "#4a148c"
            );
            const badge = document.createElement("div");
            badge.className = "rfp-score-badge";
            badge.style.background = color;
            badge.innerHTML = `<span class="rfp-score-num">${score}</span><span class="rfp-score-label">/ 100</span>`;
            matchBody.prepend(badge);
          }

          // 출처
          if (data.sources?.length) {
            const list = document.getElementById("matchSourcesList");
            list.innerHTML = data.sources.map(s =>
              `<li class="src-item">
                <span class="src-index">[${s.index}]</span>
                <span class="src-filename">${escHtml(s.filename)}</span>
                <span class="src-badge src-badge--${s.chunk_type}">${s.chunk_type === "summary" ? "개요" : "세부"}</span>
              </li>`
            ).join("");
            matchSources.style.display = "block";
          }
          matchSection.scrollIntoView({ behavior: "smooth" });

        } else if (data.type === "error") {
          matchProgress.style.display = "none";
          matchBody.style.display     = "block";
          matchBody.innerHTML = `<p style="color:#c62828">오류: ${escHtml(data.message)}</p>`;
        }
      }
    }
  } catch (e) {
    document.getElementById("matchProgMsg").textContent = `네트워크 오류: ${e.message}`;
  }
}
