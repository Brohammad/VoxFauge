const runBtn = document.getElementById("run-demo");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const credsEl = document.getElementById("demo-creds");

function demoDisabledMessage() {
  return (
    "Public demo is disabled. Set DEMO_ENABLED=true in .env and restart the server, " +
    "or use the operator dashboard after registering an account."
  );
}

async function runDemo() {
  runBtn.disabled = true;
  statusEl.textContent = "Running production pipeline demo…";
  resultsEl.classList.add("hidden");

  try {
    const res = await fetch("/api/v1/demo/quickstart", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 404 && data.detail === "Demo is not enabled") {
        throw new Error(demoDisabledMessage());
      }
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
    if (res.status === 404) {
      runBtn.disabled = true;
      statusEl.textContent = demoDisabledMessage();
      if (credsEl) {
        credsEl.textContent = "Demo disabled — see status message above";
      }
      return;
    }
    if (!res.ok) return;
    const data = await res.json();
    if (credsEl && data.email && data.password_hint) {
      credsEl.textContent = `${data.email} / ${data.password_hint}`;
    }
    runBtn.disabled = false;
  } catch {
    // Network errors are surfaced when the user clicks Run.
  }
}

loadDemoInfo();
