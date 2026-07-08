const API = "/api/v1/dashboard";
let token = localStorage.getItem("voxforge_token") || "";
let trendDays = Number(localStorage.getItem("voxforge_trend_days") || 7);

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
  outcomesTrendChart: document.getElementById("outcomes-trend-chart"),
  outcomesTrendTitle: document.getElementById("outcomes-trend-title"),
  activityList: document.getElementById("activity-list"),
  pageTitle: document.getElementById("page-title"),
  onboardingStartBtn: document.getElementById("onboarding-start-btn"),
  onboardingConnectBtn: document.getElementById("onboarding-connect-btn"),
  onboardingSampleBtn: document.getElementById("onboarding-sample-btn"),
  onboardingStatusBtn: document.getElementById("onboarding-status-btn"),
  onboardingStatus: document.getElementById("onboarding-status"),
  onboardingJson: document.getElementById("onboarding-json"),
  alertsSummary: document.getElementById("alerts-summary"),
  alertsList: document.getElementById("alerts-list"),
  replaySessionInput: document.getElementById("replay-session-input"),
  replayLoadBtn: document.getElementById("replay-load-btn"),
  replayOutcome: document.getElementById("replay-outcome"),
  replayExplanations: document.getElementById("replay-explanations"),
  replayTimeline: document.getElementById("replay-timeline"),
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

function fmtPct(v) {
  return `${Math.round((v || 0) * 100)}%`;
}

function shortId(id) {
  return id ? id.slice(0, 8) + "…" : "—";
}

function setTrendDays(days) {
  trendDays = days === 30 ? 30 : 7;
  localStorage.setItem("voxforge_trend_days", String(trendDays));
  document.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.days) === trendDays);
  });
  if (els.outcomesTrendTitle) {
    els.outcomesTrendTitle.textContent = `Outcome Trends (${trendDays}d)`;
  }
}

async function loadOverview() {
  const [d, outcomes] = await Promise.all([
    api("/overview"),
    api(`/outcomes?days=${trendDays}`),
  ]);
  els.overviewCards.innerHTML = [
    card("Total Sessions", d.total_sessions, `${d.active_sessions} active`),
    card("Messages", d.total_messages),
    card("Tool Calls", d.total_tool_calls),
    card("Evaluations", d.total_evaluations, `${d.failed_evaluations} failed`),
    card("Avg E2E Latency", fmtMs(d.avg_e2e_latency_ms)),
    card("Avg Eval Score", fmtScore(d.avg_evaluation_score)),
    card("Est. Total Cost", fmtCost(d.estimated_total_cost_usd)),
    card("Task Success Rate", fmtPct(outcomes.task_success_rate)),
    card("Escalation Rate", fmtPct(outcomes.escalation_rate)),
    card("Avg Resolution Time", `${Math.round(outcomes.avg_resolution_time_seconds || 0)}s`),
  ].join("");
  renderOutcomeTrend(outcomes.trend || []);
}

function renderOutcomeTrend(trendPoints) {
  if (!els.outcomesTrendChart) return;
  if (!trendPoints.length) {
    els.outcomesTrendChart.innerHTML = "<p>No outcome trend data yet</p>";
    return;
  }

  const points = [...trendPoints].sort((a, b) => a.day.localeCompare(b.day));
  els.outcomesTrendChart.innerHTML = points.map((point) => `
    <div class="trend-row">
      <div class="trend-label">${point.day}</div>
      <div class="trend-values">
        <span class="trend-pill">Sessions: ${point.total_sessions}</span>
        <span class="trend-pill">Success: ${fmtPct(point.task_success_rate)}</span>
        <span class="trend-pill">Escalation: ${fmtPct(point.escalation_rate)}</span>
      </div>
    </div>
  `).join("");
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
      <td><button type="button" class="link-btn" data-replay-id="${s.id}">Replay</button></td>
    </tr>
  `).join("") || "<tr><td colspan='7'>No sessions yet</td></tr>";

  els.sessionsBody.querySelectorAll("[data-replay-id]").forEach((btn) => {
    btn.addEventListener("click", () => openReplay(btn.dataset.replayId));
  });
}

function showSection(section) {
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.section === section);
  });
  document.querySelectorAll(".section").forEach((node) => node.classList.add("hidden"));
  const target = document.getElementById(section);
  if (target) target.classList.remove("hidden");
  const activeLink = document.querySelector(`.nav-link[data-section="${section}"]`);
  els.pageTitle.textContent = activeLink ? activeLink.textContent : section;
}

async function openReplay(sessionId) {
  if (!sessionId) return;
  els.replaySessionInput.value = sessionId;
  showSection("replay");
  await loadReplay(sessionId);
}

async function loadReplay(sessionId) {
  const id = (sessionId || els.replaySessionInput.value || "").trim();
  if (!id) {
    throw new Error("Enter a session UUID to load replay");
  }
  const res = await fetch(`/api/v1/sessions/${id}/replay`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`${res.status}: ${msg}`);
  }
  const replay = await res.json();
  renderReplay(replay);
}

function renderReplay(replay) {
  if (!els.replayOutcome || !els.replayTimeline) return;

  if (replay.outcome) {
    els.replayOutcome.textContent = [
      `Session ${shortId(replay.session_id)} (${replay.status})`,
      `intent=${replay.outcome.intent}`,
      `success=${replay.outcome.task_success}`,
      `escalation=${replay.outcome.escalation}`,
      `resolution=${Math.round(replay.outcome.resolution_time_seconds)}s`,
    ].join(" · ");
  } else {
    els.replayOutcome.textContent = `Session ${shortId(replay.session_id)} (${replay.status}) · no outcome recorded`;
  }

  const explanations = replay.explanations || [];
  if (els.replayExplanations) {
    els.replayExplanations.innerHTML = explanations.length
      ? explanations.map((item) => `
          <div class="explain-item ${escapeHtml(item.kind)}">
            <div class="explain-kind">${escapeHtml(item.kind)}</div>
            <div class="explain-decision">${escapeHtml(item.decision)}</div>
            <div class="explain-reason">${escapeHtml(item.reason)}</div>
          </div>
        `).join("")
      : `<div class="card-sub">No explainability signals for this session.</div>`;
  }

  const events = replay.events || [];
  els.replayTimeline.innerHTML = events.map((event) => {
    const role = event.role ? ` · ${event.role}` : "";
    const status = event.status ? ` · ${event.status}` : "";
    return `
      <li class="replay-event ${event.event_type}">
        <div class="replay-event-header">
          <span class="replay-event-type">${event.event_type}</span>
          <span class="replay-event-meta">${fmtDate(event.timestamp)}${role}${status}</span>
        </div>
        <div class="replay-event-summary">${escapeHtml(event.summary || "")}</div>
      </li>
    `;
  }).join("") || "<li class='card-sub'>No timeline events for this session.</li>";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

async function loadAlerts() {
  const summary = await api(`/alerts?days=${trendDays}`);
  if (els.alertsSummary) {
    els.alertsSummary.innerHTML = [
      { label: "Active", value: summary.active_count },
      { label: "Critical", value: summary.critical_count },
      { label: "Warning", value: summary.warning_count },
    ].map((item) => `
      <div class="eval-stat">
        <div class="value">${item.value}</div>
        <div class="label">${item.label}</div>
      </div>
    `).join("");
  }
  if (els.alertsList) {
    const alerts = summary.alerts || [];
    els.alertsList.innerHTML = alerts.length
      ? alerts.map((alert) => `
          <li class="alert-item ${escapeHtml(alert.severity)}">
            <div class="alert-header">
              <span class="alert-severity">${escapeHtml(alert.severity)}</span>
              <span class="alert-code">${escapeHtml(alert.code)}</span>
            </div>
            <div class="alert-message">${escapeHtml(alert.message)}</div>
            <div class="alert-meta">
              ${escapeHtml(alert.metric)}: ${alert.observed} vs ${alert.threshold}
            </div>
          </li>
        `).join("")
      : "<li class='card-sub'>No active regression alerts.</li>";
  }
}

function renderOnboardingStatus(run) {
  if (!run) {
    els.onboardingStatus.textContent = "No onboarding run yet.";
    els.onboardingJson.textContent = "";
    return;
  }
  els.onboardingStatus.textContent = `Status: ${run.status}`;
  els.onboardingJson.textContent = JSON.stringify(run, null, 2);
}

async function callOnboarding(path, body) {
  const res = await fetch(`/api/v1/onboarding${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

async function loadOnboardingStatus() {
  const res = await fetch("/api/v1/onboarding/status", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`${res.status}: ${msg}`);
  }
  const run = await res.json();
  renderOnboardingStatus(run);
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
      loadAlerts(),
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

document.querySelectorAll(".toggle-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    setTrendDays(Number(btn.dataset.days));
    if (!token) return;
    try {
      clearError();
      await loadOverview();
    } catch (err) {
      showError(err.message);
    }
  });
});

els.onboardingStartBtn?.addEventListener("click", async () => {
  try {
    const run = await callOnboarding("/start");
    renderOnboardingStatus(run);
    await refreshAll();
  } catch (err) {
    showError(err.message);
  }
});

els.onboardingConnectBtn?.addEventListener("click", async () => {
  try {
    const run = await callOnboarding("/connect-token", { token_preview: token.slice(0, 8) });
    renderOnboardingStatus(run);
  } catch (err) {
    showError(err.message);
  }
});

els.onboardingSampleBtn?.addEventListener("click", async () => {
  try {
    const run = await callOnboarding("/run-sample-call");
    renderOnboardingStatus(run);
    await refreshAll();
  } catch (err) {
    showError(err.message);
  }
});

els.onboardingStatusBtn?.addEventListener("click", async () => {
  try {
    await loadOnboardingStatus();
  } catch (err) {
    showError(err.message);
  }
});

els.replayLoadBtn?.addEventListener("click", async () => {
  try {
    clearError();
    await loadReplay();
  } catch (err) {
    showError(err.message);
  }
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    showSection(link.dataset.section);
  });
});

setTrendDays(trendDays);

if (token) {
  refreshAll();
  loadOnboardingStatus().catch(() => {});
}

setInterval(() => { if (token) refreshAll(); }, 30000);
