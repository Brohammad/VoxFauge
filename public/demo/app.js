const runBtn = document.getElementById("run-demo");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

async function runDemo() {
  runBtn.disabled = true;
  statusEl.textContent = "Running production pipeline demo…";
  resultsEl.classList.add("hidden");

  try {
    const res = await fetch("/api/v1/demo/quickstart", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || res.statusText);
    }

    document.getElementById("out-status").textContent = data.status;
    document.getElementById("out-e2e").textContent =
      data.e2e_ms != null ? `${Math.round(data.e2e_ms)} ms` : "—";
    document.getElementById("out-session").textContent = data.session_id || "—";
    document.getElementById("out-user").textContent = data.user_transcript;
    document.getElementById("out-assistant").textContent =
      data.assistant_response || "(no assistant message recorded)";

    resultsEl.classList.remove("hidden");
    statusEl.textContent = "Demo completed using the same path as onboarding sample calls.";
  } catch (err) {
    statusEl.textContent = `Demo failed: ${err.message}`;
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runDemo);

async function loadDemoInfo() {
  try {
    const res = await fetch("/api/v1/demo/info");
    if (!res.ok) return;
    const data = await res.json();
    const creds = document.getElementById("demo-creds");
    if (creds && data.email && data.password_hint) {
      creds.textContent = `${data.email} / ${data.password_hint}`;
    }
  } catch {
    // Demo info is optional when demo is disabled.
  }
}

loadDemoInfo();
