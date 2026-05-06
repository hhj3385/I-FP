// I&FP Frontend Logic
// ── 공고 수집 ────────────────────────────────────────────────────────────────
const collectBtn   = document.getElementById("collectBtn");
const announcePanel = document.getElementById("announcePanel");
const announceList  = document.getElementById("announceList");
const announceCount = document.getElementById("announceCount");
const navAnnounce   = document.getElementById("navAnnounce");

// ── 필터 상태 ────────────────────────────────────────────────────────────────
const filterState = { q: "", org: "", date_from: "", date_to: "", min_budget: 0 };

function getFilterParams() {
  const p = new URLSearchParams();
  if (filterState.q)          p.set("q",          filterState.q);
  if (filterState.org)        p.set("org",        filterState.org);
  if (filterState.date_from)  p.set("date_from",  filterState.date_from);
  if (filterState.date_to)    p.set("date_to",    filterState.date_to);
  if (filterState.min_budget) p.set("min_budget", filterState.min_budget);
  return p.toString() ? "?" + p.toString() : "";
}

async function loadAnnouncements() {
  try {
    const res  = await fetch("/api/announcements" + getFilterParams());
    const data = await res.json();
    const total = data.total ?? data.count;
    const shown = (data.items || []).length;
    announceCount.textContent = total === shown
      ? `${total}건`
      : `${shown}건 / 전체 ${total}건`;
    renderAnnouncements(data.items || [], filterState.q);
  } catch (e) {
    announceList.innerHTML = `<p class="announce-empty">불러오기 실패: ${e.message}</p>`;
  }
}

function highlight(text, q) {
  if (!q || !text) return text || "";
  const safe = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return text.replace(new RegExp(`(${safe})`, "gi"), "<mark>$1</mark>");
}

function renderAnnouncements(items, q = "") {
  if (!items.length) {
    announceList.innerHTML = '<p class="announce-empty">조건에 맞는 공고가 없습니다.</p>';
    return;
  }
  announceList.innerHTML = items.map(item => {
    const budget = item.presmptPrce
      ? Number(item.presmptPrce).toLocaleString() + "원"
      : "미정";
    const ntceDt = (item.bidNtceDt || "").slice(0, 10);
    const closeDt = (item.bidClseDt || "").slice(0, 10);
    const name = highlight(item.bidNtceNm || "(공고명 없음)", q);
    const org  = highlight(item.ntceInsttNm || "", q);
    return `
    <div class="announce-item" onclick="askAboutAnnouncement('${(item.bidNtceNm||'').replace(/'/g,"\\'")}')">
      <div class="ann-name">${name}</div>
      <div class="ann-meta">
        <span>🏢 ${org}</span>
        <span>📅 공고 ${ntceDt}</span>
        <span>⏰ 마감 ${closeDt}</span>
        <span class="ann-budget">💰 ${budget}</span>
      </div>
    </div>`;
  }).join("");
}

// ── 필터 UI 이벤트 ────────────────────────────────────────────────────────────
document.getElementById("filterApplyBtn")?.addEventListener("click", applyFilter);
document.getElementById("filterResetBtn")?.addEventListener("click", resetFilter);
["filterQ", "filterOrg"].forEach(id => {
  document.getElementById(id)?.addEventListener("keydown", e => {
    if (e.key === "Enter") applyFilter();
  });
});

document.querySelectorAll(".ann-ftag").forEach(tag => {
  tag.addEventListener("click", () => {
    const q = tag.dataset.q;
    document.getElementById("filterQ").value = q;
    filterState.q = q;
    document.querySelectorAll(".ann-ftag").forEach(t => t.classList.remove("active"));
    tag.classList.add("active");
    loadAnnouncements();
  });
});

function applyFilter() {
  filterState.q          = (document.getElementById("filterQ")?.value || "").trim();
  filterState.org        = (document.getElementById("filterOrg")?.value || "").trim();
  filterState.date_from  = document.getElementById("filterDateFrom")?.value || "";
  filterState.date_to    = document.getElementById("filterDateTo")?.value || "";
  const mb = parseInt(document.getElementById("filterMinBudget")?.value || "0");
  filterState.min_budget = isNaN(mb) ? 0 : mb * 10000;  // 만원 → 원
  document.querySelectorAll(".ann-ftag").forEach(t => t.classList.remove("active"));
  loadAnnouncements();
}

function resetFilter() {
  filterState.q = "";
  filterState.org = "";
  filterState.date_from = "";
  filterState.date_to = "";
  filterState.min_budget = 0;
  document.getElementById("filterQ").value = "";
  document.getElementById("filterOrg").value = "";
  document.getElementById("filterDateFrom").value = "";
  document.getElementById("filterDateTo").value = "";
  document.getElementById("filterMinBudget").value = "";
  document.querySelectorAll(".ann-ftag").forEach(t => t.classList.remove("active"));
  loadAnnouncements();
}

function askAboutAnnouncement(name) {
  const q = `"${name}" 공고에 우리 회사가 지원할 수 있는지 역량 매칭 분석을 해줘`;
  document.getElementById("question").value = q;
  announcePanel.style.display = "none";
  document.querySelector(".hero").scrollIntoView({ behavior: "smooth" });
  document.getElementById("question").focus();
}

if (collectBtn) {
  collectBtn.addEventListener("click", async () => {
    collectBtn.disabled = true;
    collectBtn.classList.add("collecting");
    collectBtn.textContent = "수집 중...";
    try {
      const res  = await fetch("/api/collect", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        alert(`${data.message}`);
        await loadAnnouncements();
      } else {
        alert(`오류: ${data.error}`);
      }
    } catch (e) {
      alert(`네트워크 오류: ${e.message}`);
    } finally {
      collectBtn.disabled = false;
      collectBtn.classList.remove("collecting");
      collectBtn.textContent = "공고 수집";
    }
  });
}

if (navAnnounce) {
  navAnnounce.addEventListener("click", async (e) => {
    e.preventDefault();
    announcePanel.style.display =
      announcePanel.style.display === "none" ? "block" : "none";
    if (announcePanel.style.display === "block") {
      await loadAnnouncements();
      announcePanel.scrollIntoView({ behavior: "smooth" });
    }
  });
}

document.getElementById("newSessionBtn")?.addEventListener("click", () => {
  threadId = null;
  document.getElementById("question").value = "";
  document.getElementById("answerSection").style.display = "none";
  document.getElementById("pipeline").style.display = "none";
  document.querySelector(".hero").scrollIntoView({ behavior: "smooth" });
});


const $ = (id) => document.getElementById(id);
const askBtn = $("askBtn");
const questionInput = $("question");
const pipeline = $("pipeline");
const answerSection = $("answerSection");
const answerBody = $("answerBody");
const metaType = $("metaType");
const metaIter = $("metaIter");

const NODE_LABELS = {
  formalizer: "질문 정식화",
  planner: "검색 계획",
  retrieval: "문서 검색",
  generator: "답변 생성",
  review: "자기 검토",
  final: "최종 정리",
};

const TYPE_LABELS = {
  rfp_analysis: "RFP 분석",
  proposal_draft: "제안서 작성",
  company_match: "역량 매칭",
  general: "일반 질문",
};

let threadId = null;
let _lastFeedbackCtx = { question: "", answer: "", questionType: "" };

// 빠른 태그 클릭
document.querySelectorAll(".tag").forEach(tag => {
  tag.addEventListener("click", () => {
    questionInput.value = tag.dataset.q;
    questionInput.focus();
  });
});

// Enter 키로 질문하기
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !askBtn.disabled) ask();
});

askBtn.addEventListener("click", ask);

function resetPipelineUI() {
  document.querySelectorAll(".pipe-step").forEach(s => {
    s.classList.remove("active", "done");
  });
}

function markStep(node, status) {
  const el = document.querySelector(`.pipe-step[data-node="${node}"]`);
  if (!el) return;
  if (status === "active") {
    document.querySelectorAll(".pipe-step.active").forEach(s => {
      s.classList.remove("active");
      s.classList.add("done");
    });
    el.classList.add("active");
  } else if (status === "done") {
    el.classList.remove("active");
    el.classList.add("done");
  }
}

// 간단 마크다운 렌더링
function renderMarkdown(md) {
  if (!md) return "";
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 헤더
  html = html.replace(/^####\s+(.*)$/gm, "<h4>$1</h4>");
  html = html.replace(/^###\s+(.*)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.*)$/gm, "<h1>$1</h1>");

  // bold/italic/code
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`(.+?)`/g, "<code>$1</code>");

  // 리스트 (간단)
  html = html.replace(/^(\s*)-\s+(.*)$/gm, "$1• $2");

  // 줄바꿈
  html = html.split(/\n\n+/).map(p => {
    if (p.match(/^<h[1-4]>/)) return p;
    return "<p>" + p.replace(/\n/g, "<br>") + "</p>";
  }).join("\n");

  return html;
}

// ── 추천 질문 렌더링 (OOD·인사 응답 시) ─────────────────────────────────────
function renderSuggestions(suggestions) {
  if (!suggestions || !suggestions.length) return "";
  const tags = suggestions.map(s =>
    `<button class="answer-suggest-tag" onclick="askSuggestion(${JSON.stringify(s)})">${escapeHtml(s)}</button>`
  ).join("");
  return `<div class="answer-suggestions">${tags}</div>`;
}

function askSuggestion(text) {
  questionInput.value = text;
  questionInput.dispatchEvent(new Event("input"));
  ask();
}

const SOURCE_TYPE_LABELS = {
  document:     "내부 문서",
  announcement: "수집 공고",
};

function renderSources(sources) {
  if (!sources || !sources.length) return "";
  const rows = sources.map(s => {
    const typeLabel = SOURCE_TYPE_LABELS[s.source_type] || s.source_type || "문서";
    const chunkBadge = s.chunk_type === "summary"
      ? '<span class="src-badge src-badge--summary">개요</span>'
      : s.chunk_type === "detail"
      ? '<span class="src-badge src-badge--detail">세부</span>'
      : "";
    return `<li class="src-item">
      <span class="src-index">[${s.index}]</span>
      <span class="src-filename">${escapeHtml(s.filename)}</span>
      ${chunkBadge}
      <span class="src-type">${escapeHtml(typeLabel)}</span>
    </li>`;
  }).join("");

  return `<div class="answer-sources">
    <div class="sources-title">참고 자료</div>
    <ul class="sources-list">${rows}</ul>
  </div>`;
}

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function ask() {
  const q = questionInput.value.trim();
  if (!q) {
    questionInput.focus();
    return;
  }

  askBtn.disabled = true;
  askBtn.innerHTML = '<span class="loading-dots"><span></span><span></span><span></span></span>';

  pipeline.style.display = "block";
  answerSection.style.display = "none";
  resetPipelineUI();

  try {
    const res = await fetch("/api/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, thread_id: threadId }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));

        if (data.type === "step") {
          markStep(data.node, "active");
        } else if (data.type === "done") {
          // 모든 단계 완료
          document.querySelectorAll(".pipe-step.active").forEach(s => {
            s.classList.remove("active");
            s.classList.add("done");
          });

          threadId = data.thread_id;
          _lastFeedbackCtx = {
            question: q,
            answer: data.answer,
            questionType: data.question_type,
          };
          metaType.textContent = TYPE_LABELS[data.question_type] || data.question_type || "—";
          metaIter.textContent = `검토 ${data.iteration_count}회`;
          answerBody.innerHTML = renderMarkdown(data.answer)
            + renderSuggestions(data.suggestions)
            + renderSources(data.sources || [])
            + renderFeedbackUI();
          answerSection.style.display = "block";
          answerSection.scrollIntoView({ behavior: "smooth", block: "start" });
        } else if (data.type === "error") {
          answerBody.innerHTML = `<p style="color:#c62828;">⚠ 오류: ${data.message}</p>`;
          answerSection.style.display = "block";
        }
      }
    }
  } catch (err) {
    answerBody.innerHTML = `<p style="color:#c62828;">⚠ 네트워크 오류: ${err.message}</p>`;
    answerSection.style.display = "block";
  } finally {
    askBtn.disabled = false;
    askBtn.innerHTML = "질문하기";
  }
}

// ── 피드백 UI ─────────────────────────────────────────────────────────────────
function renderFeedbackUI() {
  return `
  <div class="feedback-bar" id="feedbackBar">
    <span class="feedback-label">답변이 도움이 됐나요?</span>
    <button class="feedback-btn like" id="btnLike" onclick="onFeedbackLike()">👍 좋아요</button>
    <button class="feedback-btn dislike" id="btnDislike" onclick="onFeedbackDislike()">👎 싫어요</button>
  </div>
  <div class="feedback-form" id="feedbackForm">
    <label>어떤 점이 아쉬웠나요?</label>
    <textarea class="feedback-textarea" id="feedbackText"
      placeholder="예) 관련 사업 사례가 빠졌어요 / 답변이 너무 일반적이에요 / 출처가 맞지 않아요"></textarea>
    <div class="feedback-form-actions">
      <button class="feedback-submit" onclick="submitDislike()">피드백 전송</button>
      <button class="feedback-cancel" onclick="cancelFeedback()">취소</button>
    </div>
  </div>
  <div class="feedback-done" id="feedbackDone"></div>`;
}

function onFeedbackLike() {
  const bar = document.getElementById("feedbackBar");
  if (!bar) return;
  document.getElementById("btnLike").classList.add("selected-like");
  document.getElementById("btnDislike").disabled = true;
  document.getElementById("feedbackForm").classList.remove("open");
  sendFeedback("like", "");
}

function onFeedbackDislike() {
  const form = document.getElementById("feedbackForm");
  if (!form) return;
  document.getElementById("btnDislike").classList.add("selected-dislike");
  document.getElementById("btnLike").disabled = true;
  form.classList.add("open");
  document.getElementById("feedbackText").focus();
}

function cancelFeedback() {
  document.getElementById("feedbackForm").classList.remove("open");
  document.getElementById("btnDislike").classList.remove("selected-dislike");
  document.getElementById("btnLike").disabled = false;
}

async function submitDislike() {
  const text = (document.getElementById("feedbackText")?.value || "").trim();
  await sendFeedback("dislike", text);
}

async function sendFeedback(rating, feedbackText) {
  const done = document.getElementById("feedbackDone");
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: threadId,
        question: _lastFeedbackCtx.question,
        answer: _lastFeedbackCtx.answer,
        question_type: _lastFeedbackCtx.questionType,
        rating,
        feedback_text: feedbackText,
      }),
    });
    document.getElementById("feedbackForm")?.classList.remove("open");
    document.getElementById("feedbackBar").style.pointerEvents = "none";
    if (done) {
      done.textContent = rating === "like"
        ? "✓ 피드백 감사합니다!"
        : feedbackText
          ? "✓ 피드백이 저장됐습니다. 개선에 반영하겠습니다."
          : "✓ 피드백 감사합니다.";
      done.classList.add("show");
    }
  } catch (e) {
    if (done) { done.textContent = "피드백 저장 실패"; done.classList.add("show"); }
  }
}

// ── 학습 문서 수 동적 로드 ────────────────────────────────────────────────────
(async () => {
  try {
    const data = await fetch("/api/archive/stats").then(r => r.json());
    const el = document.getElementById("docCount");
    if (el && data.file_count) el.textContent = data.file_count.toLocaleString();
  } catch (_) {}
})();
