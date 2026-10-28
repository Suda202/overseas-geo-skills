const SAMPLE = {
  brand_name: "KeepBalance",
  company_name: "KeepBalance",
  business_mode: "B2C",
  category: "family dietary supplements",
  official_domain: "https://keepbalance.life",
  topics: "family dietary supplements",
  competitors: [
    { name: "By-Health", official_domain: "https://by-health.com" },
    { name: "WonderLab", official_domain: "https://wonderlab.top" },
    { name: "Swisse", official_domain: "https://swisse.com" },
  ],
  regions: "US",
  supplemental: "Target market US; customer-facing B2C diagnostic case.",
};

const $ = (sel) => document.querySelector(sel);
const form = $("#case-form");
const compRows = $("#comp-rows");
let lastArtifact = null;

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const which = btn.dataset.tab;
    $("#panel-form").classList.toggle("hidden", which !== "form");
    $("#panel-paste").classList.toggle("hidden", which !== "paste");
    const hist = $("#panel-history");
    if (hist) hist.classList.toggle("hidden", which !== "history");
    if (which === "history") refreshHistory();
    $("#panel-result").classList.add("hidden");
  });
});

// ---------- competitors ----------
const MAX_COMPETITORS = 6;

function addCompRow(name = "", domain = "") {
  if (compRows.querySelectorAll(".comp-row").length >= MAX_COMPETITORS) return;
  const row = document.createElement("div");
  row.className = "comp-row";
  row.innerHTML = `
    <input class="c-name" placeholder="竞品名，如 By-Health">
    <input class="c-domain" placeholder="官网，如 https://by-health.com">
    <button type="button" title="删除">×</button>`;
  row.querySelector(".c-name").value = name;
  row.querySelector(".c-domain").value = domain;
  row.querySelector("button").addEventListener("click", () => {
    row.remove();
    syncCompCount();
  });
  compRows.appendChild(row);
  syncCompCount();
}

function syncCompCount() {
  const n = compRows.querySelectorAll(".comp-row").length;
  const btn = $("#add-comp");
  btn.disabled = n >= MAX_COMPETITORS;
  btn.textContent = n >= MAX_COMPETITORS ? `已达上限（${MAX_COMPETITORS} 个）` : "+ 添加竞品";
}

$("#add-comp").addEventListener("click", () => addCompRow());

function readCompetitors() {
  return [...compRows.querySelectorAll(".comp-row")]
    .map((r) => ({
      name: r.querySelector(".c-name").value.trim(),
      official_domain: r.querySelector(".c-domain").value.trim(),
    }))
    .filter((c) => c.name);
}

// ---------- form <-> sample ----------
function fillForm(obj) {
  for (const key of [
    "brand_name", "company_name", "business_mode", "category",
    "official_domain", "topics", "regions", "supplemental",
  ]) {
    const el = form.querySelector(`[name="${key}"]`);
    if (el) el.value = obj[key] ?? "";
  }
  compRows.innerHTML = "";
  let comps = obj.competitors ?? [];
  if (typeof comps === "string") {
    try { comps = JSON.parse(comps); } catch { comps = []; }
  }
  if (!Array.isArray(comps)) comps = [];
  comps.slice(0, MAX_COMPETITORS).forEach((c) =>
    addCompRow(c.name || "", c.official_domain || c.domain || ""));
  if (comps.length === 0) addCompRow();
}

$("#load-sample").addEventListener("click", () => fillForm(SAMPLE));

// ---------- run ----------
function setStatus(msg, kind = "") {
  const s = $("#status");
  s.textContent = msg;
  s.className = "status" + (kind ? " " + kind : "");
}

function renderArtifact(art) {
  $("#panel-result").classList.remove("hidden");
  $("#result-actions").classList.remove("hidden");
  $("#meta").textContent =
    `${art.question_count} 题 · ${art.schema_version} · run ${art.run_id}`;
  $("#questions").innerHTML = "";
  (art.questions || []).forEach((q, i) => {
    const card = document.createElement("div");
    card.className = "q-card";
    const tags = (q.tags || []).map((t) => `<span class="tag">${t}</span>`).join("");
    card.innerHTML = `
      <p class="q-text">${i + 1}. ${q.user_question ?? q.question ?? ""}</p>
      <div class="q-meta">${q.intent_key ?? ""}</div>
      <div class="tags">${tags}</div>`;
    $("#questions").appendChild(card);
  });

  const blob = new Blob([JSON.stringify(art, null, 2)], { type: "application/json" });
  $("#dl").href = URL.createObjectURL(blob);
  $("#output").textContent = JSON.stringify(art, null, 2);
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
  return data;
}

async function runCase(caseObj) {
  $("#panel-result").classList.remove("hidden");
  $("#result-actions").classList.add("hidden");
  $("#questions").innerHTML = "";
  $("#output").classList.add("hidden");
  const started = Date.now();
  setStatus("运行中… 完整流程需要几分钟");
  const timer = setInterval(() => {
    setStatus(`运行中… 已等待 ${Math.round((Date.now() - started) / 1000)}s`);
  }, 1000);

  const btn = $("#run-btn");
  btn.disabled = true;
  try {
    const sub = await postJSON("/api/v1/runs", { case: caseObj });
    const art = await fetch(sub.artifact_url).then((r) => r.json());
    clearInterval(timer);
    setStatus(`完成，用时 ${Math.round((Date.now() - started) / 1000)}s`, "ok");
    lastArtifact = art;
    renderArtifact(art);
    refreshHistory();
  } catch (e) {
    clearInterval(timer);
    setStatus(`失败：${e.message}`, "error");
  } finally {
    btn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const data = {};
  for (const el of form.querySelectorAll("input[name], textarea[name]")) {
    data[el.name] = el.value.trim();
  }
  data.competitors = readCompetitors();
  runCase(data);
});

// ---------- paste ----------
$("#paste-to-form").addEventListener("click", () => {
  try {
    const obj = JSON.parse($("#paste-box").value);
    fillForm(obj.case ?? obj.inputs ?? obj);
    document.querySelector('.tab[data-tab="form"]').click();
  } catch {
    $("#paste-hint").textContent = "不是合法 JSON";
  }
});

$("#paste-box").addEventListener("input", () => {
  const raw = $("#paste-box").value.trim();
  if (!raw) { $("#paste-hint").textContent = ""; return; }
  try {
    JSON.parse(raw);
    $("#paste-hint").textContent = "JSON 合法";
  } catch {
    $("#paste-hint").textContent = "JSON 尚不完整（提交时还会尝试容错解析）";
  }
});

$("#paste-run").addEventListener("click", async () => {
  const raw = $("#paste-box").value;
  if (!raw.trim()) { $("#paste-hint").textContent = "内容为空"; return; }
  $("#panel-result").classList.remove("hidden");
  $("#result-actions").classList.add("hidden");
  $("#questions").innerHTML = "";
  $("#output").classList.add("hidden");
  const started = Date.now();
  setStatus("运行中… 完整流程需要几分钟");
  const timer = setInterval(() => {
    setStatus(`运行中… 已等待 ${Math.round((Date.now() - started) / 1000)}s`);
  }, 1000);
  try {
    const sub = await postJSON("/api/v1/runs/paste", { raw });
    const art = await fetch(sub.artifact_url).then((r) => r.json());
    clearInterval(timer);
    setStatus(`完成，用时 ${Math.round((Date.now() - started) / 1000)}s`, "ok");
    lastArtifact = art;
    renderArtifact(art);
    refreshHistory();
  } catch (e) {
    clearInterval(timer);
    setStatus(`失败：${e.message}`, "error");
  }
});

// ---------- history ----------
let historyPage = 1;
const HISTORY_PAGE_SIZE = 10;

function fmtRunTime(runId) {
  // "20261027T101845Z-abc123" -> "2026-10-27 18:18:45"（本地时区）
  const stamp = (runId || "").split("-")[0];
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(stamp);
  if (!m) return runId;
  const [, y, mo, d, h, mi, s] = m;
  const local = new Date(Date.UTC(+y, +mo - 1, +d, +h, +mi, +s));
  const pad = (n) => String(n).padStart(2, "0");
  return `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())} ` +
         `${pad(local.getHours())}:${pad(local.getMinutes())}:${pad(local.getSeconds())}`;
}

function renderRuns(payload) {
  const runs = payload.runs || [];
  const tbody = $("#runs-tbody");
  const table = $("#panel-history table.runs");
  const empty = $("#runs-empty");
  tbody.innerHTML = "";
  if (!runs.length) {
    table.classList.add("hidden");
    $("#pager").classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }
  table.classList.remove("hidden");
  empty.classList.add("hidden");

  runs.forEach((r) => {
    const tr = document.createElement("tr");
    let badge = '<span class="badge">进行中</span>';
    if (r.has_artifact) badge = '<span class="badge ok">成功</span>';
    else if (r.has_error) badge = `<span class="badge err">${r.error_kind || "失败"}</span>`;
    const qc = r.question_count === undefined ? "—" : r.question_count;
    tr.innerHTML = `
      <td class="mono"></td>
      <td><span class="brand"></span></td>
      <td class="ellipsis" title=""></td>
      <td></td>
      <td class="num">${qc}</td>
      <td>${badge}</td>
      <td><a class="view-link" href="/runs/${r.run_id}">查看 →</a></td>`;
    tr.querySelector(".mono").textContent = fmtRunTime(r.run_id);
    const brand = tr.querySelector(".brand");
    brand.textContent = r.brand_name || "—";
    if (r.brand_name) brand.classList.add("brand-strong");
    const cat = tr.querySelector(".ellipsis");
    cat.textContent = r.category || "—";
    cat.title = r.category || "";
    tr.children[3].textContent = r.regions || "—";
    tbody.appendChild(tr);
  });

  // pager
  const total = payload.total || 0;
  const totalPages = payload.total_pages || 1;
  const pager = $("#pager");
  if (total > HISTORY_PAGE_SIZE) {
    pager.classList.remove("hidden");
    $("#page-info").textContent = `第 ${payload.page} / ${totalPages} 页 · 共 ${total} 条`;
    $("#prev-page").disabled = payload.page <= 1;
    $("#next-page").disabled = payload.page >= totalPages;
  } else {
    pager.classList.add("hidden");
  }
}

async function refreshHistory(page) {
  if (page !== undefined) historyPage = page;
  try {
    const d = await fetch(`/api/v1/runs?page=${historyPage}&page_size=${HISTORY_PAGE_SIZE}`)
      .then((r) => r.json());
    renderRuns(d);
  } catch { /* history is best-effort */ }
}

$("#prev-page")?.addEventListener("click", () => refreshHistory(historyPage - 1));
$("#next-page")?.addEventListener("click", () => refreshHistory(historyPage + 1));
$("#history-refresh")?.addEventListener("click", () => refreshHistory());

// ---------- result actions ----------
// navigator.clipboard 只在安全上下文（HTTPS / localhost）可用。
// 内网用 http://<ip>:8080 访问时必须走 execCommand 兜底。
async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch { /* 落到下面的兜底 */ }
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0";
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  document.body.removeChild(ta);
  return ok;
}

$("#copy").addEventListener("click", async () => {
  if (!lastArtifact) {
    $("#copy").textContent = "暂无内容";
    setTimeout(() => ($("#copy").textContent = "复制"), 1500);
    return;
  }
  const ok = await copyText(JSON.stringify(lastArtifact, null, 2));
  $("#copy").textContent = ok ? "已复制" : "复制失败";
  setTimeout(() => ($("#copy").textContent = "复制"), 1500);
});

$("#toggle-raw").addEventListener("click", () => {
  $("#output").classList.toggle("hidden");
  $("#questions").classList.toggle("hidden");
  $("#toggle-raw").textContent =
    $("#output").classList.contains("hidden") ? "查看原始" : "查看卡片";
});

// ---------- health ----------
$("#health").addEventListener("click", async (e) => {
  e.preventDefault();
  const el = $("#health");
  el.textContent = "检查中…";
  try {
    const h = await fetch("/healthz").then((r) => r.json());
    el.textContent = h.auth_ok ? "Dify ✓" : "Dify ✗";
    el.title = `base: ${h.dify_base_url}\nauth: ${h.auth_detail || "ok"}`;
  } catch {
    el.textContent = "Dify 不可达";
  }
});

addCompRow();
