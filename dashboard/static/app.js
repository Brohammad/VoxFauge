const API = "/api/v1/dashboard";
let token = localStorage.getItem("voxforge_token") || "";

const els = {
  tokenInput: document.getElementById("token-input"),
  connectBtn: document.getElementById("connect-btn"),
  authStatus: document.getElementById("auth-status"),
  errorBanner: document.getElementById("error-banner"),
  overviewCards: document.getElementById("overview-cards"),
  sessionsBody: document.getElementById("sessions-body"),
  latencyChart: document.getElementById("latency-chart"),
  evalSummary: document.getElementById("eval-summary"),
  evalMetrics: document.getElementById("eval-metrics"),
  activityList: document.getElementById("activity-list"),
  pageTitle: document.getElementById("page-title"),
};

els.tokenInput.value = token;

async function api(path) {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove("hidden");
}

function clearError() {
  els.errorBanner.classList.add("hidden");
}

function setConnected(ok) {
  els.authStatus.textContent = ok ? "Connected" : "Not connected";
  els.authStatus.classList.toggle("connected", ok);
}

function card(label, value, sub = "") {
  return `<div class="card"><div class="card-label">${label}</div><div class="card-value">${value}</div>${sub ? `<div class="card-sub">${sub}</div>` : ""}</div>`;
}

function fmtMs(v) {
  return v != null ? `${Math.round(v)} ms` : "—";
}

function fmtScore(v) {
  return v != null ? v.toFixed(2) : "—";
}

function fmtCost(v) {
  return v != null ? `$${v.toFixed(4)}` : "—";
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function shortId(id) {
  return id ? id.slice(0, 8) + "…" : "—";
}

async function loadOverview() {
  const d = await api("/overview");
  els.overviewCards.innerHTML = [
    card("Total Sessions", d.total_sessions, `${d.active_sessions} active`),
    card("Messages", d.total_messages),
    card("Tool Calls", d.total_tool_calls),
    card("Evaluations", d.total_evaluations, `${d.failed_evaluations} failed`),
    card("Avg E2E Latency", fmtMs(d.avg_e2e_latency_ms)),
    card("Avg Eval Score", fmtScore(d.avg_evaluation_score)),
    card("Est. Total Cost", fmtCost(d.estimated_total_cost_usd)),
  ].join("");
}

async function loadSessions() {
  const sessions = await api("/sessions?limit=20");
  els.sessionsBody.innerHTML = sessions.map((s) => `
    <tr>
      <td><code>${shortId(s.id)}</code></td>
      <td><span class="status-pill ${s.status}">${s.status}</span></td>
      <td>${s.message_count}</td>
      <td>${fmtMs(s.avg_e2e_ms)}</td>
      <td>${fmtScore(s.last_evaluation_score)}</td>
      <td>${fmtDate(s.started_at)}</td>
    </tr>
  `).join("") || "<tr><td colspan='6'>No sessions yet</td></tr>";
}

async function loadLatency() {
  const buckets = await api("/latency");
  const max = Math.max(...buckets.map((b) => b.avg_ms), 1);
  els.latencyChart.innerHTML = buckets.map((b) => {
    const pct = Math.max(8, (b.avg_ms / max) * 100);
    return `<div class="bar-row">
      <div class="bar-label">${b.metric_name.replace(/_/g, " ")}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%">${Math.round(b.avg_ms)} ms</div></div>
    </div>`;
  }).join("") || "<p>No latency data yet</p>";
}

async function loadEvaluations() {
  const e = await api("/evaluations");
  els.evalSummary.innerHTML = [
    { label: "Total Runs", value: e.total_runs },
    { label: "Avg Score", value: fmtScore(e.avg_score) },
    { label: "Passed", value: e.passed },
    { label: "Warning", value: e.warning },
    { label: "Failed", value: e.failed },
  ].map((s) => `<div class="eval-stat"><div class="value">${s.value}</div><div class="label">${s.label}</div></div>`).join("");

  const metrics = Object.entries(e.by_metric || {});
  els.evalMetrics.innerHTML = metrics.map(([name, score]) => {
    const pct = Math.round(score * 100);
    return `<div class="bar-row">
      <div class="bar-label">${name.replace(/_/g, " ")}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%">${score.toFixed(2)}</div></div>
    </div>`;
  }).join("") || "<p>No evaluation metrics yet</p>";
}

async function loadActivity() {
  const items = await api("/activity?limit=30");
  els.activityList.innerHTML = items.map((i) => `
    <li>
      <span><span class="activity-type">${i.type}</span>${i.summary}</span>
      <span class="activity-time">${fmtDate(i.timestamp)}</span>
    </li>
  `).join("") || "<li>No recent activity</li>";
}

async function refreshAll() {
  if (!token) return;
  clearError();
  try {
    await Promise.all([
      loadOverview(),
      loadSessions(),
      loadLatency(),
      loadEvaluations(),
      loadActivity(),
    ]);
    setConnected(true);
  } catch (err) {
    setConnected(false);
    showError(err.message);
  }
}

els.connectBtn.addEventListener("click", () => {
  token = els.tokenInput.value.trim();
  localStorage.setItem("voxforge_token", token);
  refreshAll();
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const section = link.dataset.section;
    document.querySelectorAll(".nav-link").forEach((l) => l.classList.remove("active"));
    link.classList.add("active");
    document.querySelectorAll(".section").forEach((s) => s.classList.add("hidden"));
    document.getElementById(section).classList.remove("hidden");
    els.pageTitle.textContent = link.textContent;
  });
});

if (token) refreshAll();

setInterval(() => { if (token) refreshAll(); }, 30000);
