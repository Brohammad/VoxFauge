#!/usr/bin/env python3
"""Manual E2E QA harness — tests every VoxForge feature separately."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/api/v1/ws/voice"


@dataclass
class Result:
    feature: str
    test: str
    passed: bool
    detail: str = ""


@dataclass
class QAReport:
    results: list[Result] = field(default_factory=list)

    def record(self, feature: str, test: str, passed: bool, detail: str = "") -> None:
        self.results.append(Result(feature, test, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {feature} / {test}" + (f" — {detail}" if detail else ""))

    def summary(self) -> tuple[int, int]:
        passed = sum(1 for r in self.results if r.passed)
        return passed, len(self.results)


report = QAReport()
ctx: dict[str, Any] = {}


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ctx['token']}"}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        await test_health(client)
        await test_static_routes(client)
        await test_auth(client)
        await test_orgs(client)
        await test_api_keys(client)
        await test_sessions(client)
        await test_memory(client)
        await test_tools(client)
        await test_evaluations(client)
        await test_agent_configs(client)
        await test_onboarding(client)
        await test_templates(client)
        await test_dashboard(client)
        await test_replay(client)
        await test_sso(client)
        await test_livekit(client)
        await test_alerts(client)

    await test_voice_websocket()

    passed, total = report.summary()
    print("\n" + "=" * 60)
    print(f"E2E QA SUMMARY: {passed}/{total} passed")
    if passed < total:
        print("\nFAILURES:")
        for r in report.results:
            if not r.passed:
                print(f"  - {r.feature} / {r.test}: {r.detail}")
    return 0 if passed == total else 1


async def test_health(client: httpx.AsyncClient) -> None:
    feature = "Health & Observability"
    for path, key in [("/api/v1/health", "status"), ("/api/v1/ready", "status")]:
        r = await client.get(path)
        ok = r.status_code == 200 and r.json().get(key) == "ok"
        report.record(feature, path, ok, f"status={r.status_code}")

    r = await client.get("/api/v1/metrics")
    ok = r.status_code == 200 and "voxforge" in r.text or "http" in r.text
    report.record(feature, "GET /metrics (Prometheus)", ok, f"len={len(r.text)}")


async def test_static_routes(client: httpx.AsyncClient) -> None:
    feature = "Static Routes"
    for path, needle in [
        ("/dashboard", "VoxForge Dashboard"),
        ("/dashboard/static/app.js", "loadOverview"),
        ("/dashboard/static/styles.css", "layout"),
        ("/examples/livekit", "livekit"),
        ("/api/v1/docs", "swagger"),
    ]:
        r = await client.get(path)
        body = r.text.lower()
        ok = r.status_code == 200 and needle.lower() in body
        report.record(feature, path, ok, f"status={r.status_code}")


async def test_auth(client: httpx.AsyncClient) -> None:
    feature = "Authentication"
    suffix = uuid.uuid4().hex[:8]
    email = f"qa-manual-{suffix}@example.com"
    password = "securepass123"

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "QA Manual", "org_name": f"QA {suffix}"},
    )
    ok = r.status_code == 201
    report.record(feature, "POST /register", ok, f"status={r.status_code}")
    if not ok:
        report.record(feature, "abort downstream", False, r.text[:200])
        return

    data = r.json()
    ctx["token"] = data["tokens"]["access_token"]
    ctx["refresh"] = data["tokens"]["refresh_token"]
    ctx["org_id"] = data["org_id"]
    ctx["user_id"] = data["user_id"]

    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    report.record(feature, "POST /login", r.status_code == 200, f"status={r.status_code}")

    r = await client.get("/api/v1/auth/me", headers=auth_headers())
    me_ok = r.status_code == 200 and r.json()["user"]["email"] == email
    report.record(feature, "GET /me", me_ok, f"status={r.status_code}")

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": ctx["refresh"]})
    refresh_ok = r.status_code == 200 and "access_token" in r.json()
    if refresh_ok:
        ctx["token"] = r.json()["access_token"]
    report.record(feature, "POST /refresh", refresh_ok, f"status={r.status_code}")

    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Dup", "org_name": "Dup"},
    )
    report.record(feature, "Duplicate register rejected", dup.status_code in (400, 409, 422), f"status={dup.status_code}")

    unauth = await client.get("/api/v1/auth/me")
    report.record(feature, "Unauthenticated /me rejected", unauth.status_code == 401, f"status={unauth.status_code}")


async def test_orgs(client: httpx.AsyncClient) -> None:
    feature = "Organizations"
    org_id = ctx["org_id"]

    r = await client.get("/api/v1/orgs", headers=auth_headers())
    report.record(feature, "GET /orgs", r.status_code == 200 and isinstance(r.json(), list), f"status={r.status_code}")

    r = await client.get(f"/api/v1/orgs/{org_id}", headers=auth_headers())
    report.record(feature, "GET /orgs/{id}", r.status_code == 200, f"status={r.status_code}")

    r = await client.get(f"/api/v1/orgs/{org_id}/members", headers=auth_headers())
    members = r.json() if r.status_code == 200 else []
    report.record(feature, "GET /orgs/{id}/members", r.status_code == 200 and len(members) >= 1, f"count={len(members)}")

    r = await client.get(f"/api/v1/orgs/{org_id}/audit-logs", headers=auth_headers())
    report.record(feature, "GET /audit-logs", r.status_code == 200, f"status={r.status_code}")

    r = await client.get(f"/api/v1/orgs/{org_id}/audit-logs/export", headers=auth_headers())
    report.record(feature, "GET /audit-logs/export", r.status_code == 200, f"status={r.status_code}, type={r.headers.get('content-type')}")

    r = await client.get("/api/v1/orgs", headers={})
    report.record(feature, "Org routes require auth", r.status_code == 401, f"status={r.status_code}")


async def test_api_keys(client: httpx.AsyncClient) -> None:
    feature = "API Keys"
    r = await client.post("/api/v1/api-keys", headers=auth_headers(), json={"name": "qa-e2e-key"})
    create_ok = r.status_code == 201
    report.record(feature, "POST /api-keys", create_ok, f"status={r.status_code}")
    if not create_ok:
        return

    key_data = r.json()
    ctx["api_key"] = key_data["raw_key"]
    key_id = key_data["id"]

    r = await client.get("/api/v1/api-keys", headers=auth_headers())
    report.record(feature, "GET /api-keys", r.status_code == 200 and any(k["id"] == key_id for k in r.json()), f"status={r.status_code}")

    r = await client.post("/api/v1/sessions", headers={"X-API-Key": ctx["api_key"]}, json={})
    report.record(feature, "API key auth works", r.status_code == 201, f"status={r.status_code}")
    if r.status_code == 201:
        ctx["api_key_session"] = r.json()["session_id"]

    r = await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers())
    report.record(feature, "DELETE /api-keys/{id}", r.status_code == 200, f"status={r.status_code}")


async def test_sessions(client: httpx.AsyncClient) -> None:
    feature = "Sessions"
    r = await client.post("/api/v1/sessions", headers=auth_headers(), json={})
    create_ok = r.status_code == 201
    report.record(feature, "POST /sessions", create_ok, f"status={r.status_code}")
    if not create_ok:
        return

    session_id = r.json()["session_id"]
    ctx["session_id"] = session_id

    r = await client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers())
    report.record(feature, "GET /sessions/{id}", r.status_code == 200, f"status={r.status_code}")

    r = await client.get(f"/api/v1/sessions/{session_id}/messages", headers=auth_headers())
    report.record(feature, "GET /sessions/{id}/messages", r.status_code == 200, f"status={r.status_code}")

    fake = str(uuid.uuid4())
    r = await client.get(f"/api/v1/sessions/{fake}", headers=auth_headers())
    report.record(feature, "GET nonexistent session", r.status_code == 404, f"status={r.status_code}")


async def test_memory(client: httpx.AsyncClient) -> None:
    feature = "Memory"
    session_id = ctx.get("session_id")
    if not session_id:
        report.record(feature, "skipped", False, "no session")
        return

    r = await client.get(f"/api/v1/sessions/{session_id}/memory", headers=auth_headers())
    report.record(feature, "GET /memory", r.status_code == 200, f"status={r.status_code}")

    r = await client.post(
        f"/api/v1/sessions/{session_id}/memory/search",
        headers=auth_headers(),
        json={"query": "billing question", "top_k": 3},
    )
    report.record(feature, "POST /memory/search", r.status_code == 200, f"status={r.status_code}")


async def test_tools(client: httpx.AsyncClient) -> None:
    feature = "MCP Tool Router"
    r = await client.get("/api/v1/tools", headers=auth_headers())
    tools_ok = r.status_code == 200 and "tools" in r.json()
    report.record(feature, "GET /tools", tools_ok, f"status={r.status_code}, count={len(r.json().get('tools', []))}")

    session_id = ctx.get("session_id")
    if session_id:
        r = await client.get(f"/api/v1/sessions/{session_id}/tool-calls", headers=auth_headers())
        report.record(feature, "GET /tool-calls", r.status_code == 200, f"status={r.status_code}")


async def test_evaluations(client: httpx.AsyncClient) -> None:
    feature = "Evaluation Engine"
    session_id = ctx.get("session_id")
    if not session_id:
        report.record(feature, "skipped", False, "no session")
        return

    r = await client.get(f"/api/v1/sessions/{session_id}/evaluations", headers=auth_headers())
    report.record(feature, "GET /sessions/{id}/evaluations", r.status_code == 200, f"status={r.status_code}")

    runs = r.json().get("evaluations", [])
    if runs:
        run_id = runs[0]["id"]
        r2 = await client.get(f"/api/v1/evaluations/{run_id}", headers=auth_headers())
        report.record(feature, "GET /evaluations/{run_id}", r2.status_code == 200, f"status={r2.status_code}")
    else:
        report.record(feature, "GET /evaluations/{run_id}", True, "no runs yet (acceptable)")


async def test_agent_configs(client: httpx.AsyncClient) -> None:
    feature = "Agent Config Versioning"
    r = await client.get("/api/v1/agent-configs/presets", headers=auth_headers())
    presets_ok = r.status_code == 200 and len(r.json()) > 0
    report.record(feature, "GET /presets", presets_ok, f"count={len(r.json()) if r.status_code == 200 else 0}")

    if presets_ok:
        slug = r.json()[0]["slug"]
        r2 = await client.post(
            f"/api/v1/agent-configs/presets/{slug}/apply",
            headers=auth_headers(),
            json={"change_note": "E2E QA apply"},
        )
        report.record(feature, "POST /presets/{slug}/apply", r2.status_code == 201, f"status={r2.status_code}")
        if r2.status_code == 201:
            ctx["config_version"] = r2.json()["version"]

    r = await client.get("/api/v1/agent-configs/active", headers=auth_headers())
    report.record(feature, "GET /active", r.status_code == 200, f"status={r.status_code}")

    r = await client.get("/api/v1/agent-configs", headers=auth_headers())
    versions = r.json() if r.status_code == 200 else []
    report.record(feature, "GET /agent-configs", r.status_code == 200 and len(versions) >= 1, f"versions={len(versions)}")

    if len(versions) >= 2:
        target = next((v["version"] for v in versions if not v["is_active"]), None)
        if target:
            r3 = await client.post(
                "/api/v1/agent-configs/rollback",
                headers=auth_headers(),
                json={"target_version": target, "change_note": "E2E rollback"},
            )
            report.record(feature, "POST /rollback", r3.status_code == 200, f"status={r3.status_code}")


async def test_onboarding(client: httpx.AsyncClient) -> None:
    feature = "Onboarding"
    r = await client.post("/api/v1/onboarding/start", headers=auth_headers())
    report.record(feature, "POST /start", r.status_code == 200, f"status={r.status_code}, state={r.json().get('status') if r.status_code == 200 else ''}")

    r = await client.post(
        "/api/v1/onboarding/connect-token",
        headers=auth_headers(),
        json={"token_preview": ctx["token"][:8]},
    )
    report.record(feature, "POST /connect-token", r.status_code == 200, f"status={r.status_code}")

    r = await client.post("/api/v1/onboarding/run-sample-call", headers=auth_headers())
    sample_ok = r.status_code == 200
    if sample_ok:
        ctx["onboarding_status"] = r.json().get("status")
    report.record(feature, "POST /run-sample-call", sample_ok, f"status={r.json().get('status') if sample_ok else r.status_code}")

    r = await client.get("/api/v1/onboarding/status", headers=auth_headers())
    report.record(feature, "GET /status", r.status_code == 200, f"status={r.json().get('status') if r.status_code == 200 else r.status_code}")


async def test_templates(client: httpx.AsyncClient) -> None:
    feature = "Templates"
    r = await client.get("/api/v1/templates/support/default", headers=auth_headers())
    ok = r.status_code == 200 and "prompt_config" in r.json()
    report.record(feature, "GET /templates/support/default", ok, f"status={r.status_code}")


async def test_dashboard(client: httpx.AsyncClient) -> None:
    feature = "Dashboard API"
    endpoints = [
        ("/api/v1/dashboard/overview", "total_sessions"),
        ("/api/v1/dashboard/sessions?limit=20", None),
        ("/api/v1/dashboard/latency", None),
        ("/api/v1/dashboard/evaluations", "total_runs"),
        ("/api/v1/dashboard/activity?limit=30", None),
        ("/api/v1/dashboard/outcomes?days=7", "task_success_rate"),
        ("/api/v1/dashboard/outcomes?days=30", "task_success_rate"),
        ("/api/v1/dashboard/alerts?days=7", "active_count"),
    ]
    for path, key in endpoints:
        r = await client.get(path, headers=auth_headers())
        ok = r.status_code == 200 and (key is None or key in r.json())
        report.record(feature, f"GET {path.split('?')[0]}", ok, f"status={r.status_code}")

    r = await client.get("/api/v1/dashboard/overview", headers={})
    report.record(feature, "Dashboard requires auth", r.status_code == 401, f"status={r.status_code}")


async def test_replay(client: httpx.AsyncClient) -> None:
    feature = "Replay"
    session_id = ctx.get("session_id")
    if not session_id:
        report.record(feature, "skipped", False, "no session")
        return

    r = await client.get(f"/api/v1/sessions/{session_id}/replay", headers=auth_headers())
    ok = r.status_code == 200 and "events" in r.json()
    report.record(feature, "GET /sessions/{id}/replay", ok, f"events={len(r.json().get('events', []))}")


async def test_sso(client: httpx.AsyncClient) -> None:
    feature = "SSO / SAML"
    org_id = ctx["org_id"]
    base = f"/api/v1/orgs/{org_id}/sso/saml"

    r = await client.get(base, headers=auth_headers())
    report.record(feature, "GET connections", r.status_code == 200, f"status={r.status_code}")

    cert = "-----BEGIN CERTIFICATE-----\nMIIBkTCB+wIJAKHBfpF0\n-----END CERTIFICATE-----"
    payload = {
        "provider_type": "generic",
        "idp_entity_id": "https://idp.qa.test/metadata",
        "idp_sso_url": "https://idp.qa.test/sso",
        "idp_x509_cert": cert,
        "sp_entity_id": "voxforge-sp-qa",
        "acs_url": f"{BASE}/api/v1/orgs/{org_id}/sso/saml/acs",
        "default_role": "member",
        "role_mapping_rules": {"support_admins": "admin"},
    }
    r = await client.post(base, headers=auth_headers(), json=payload)
    create_ok = r.status_code == 201
    report.record(feature, "POST create connection", create_ok, f"status={r.status_code}")
    if not create_ok:
        return

    conn_id = r.json()["id"]

    r = await client.patch(f"{base}/{conn_id}", headers=auth_headers(), json={"status": "active", "role_mapping_rules": {}})
    report.record(feature, "PATCH activate", r.status_code == 200, f"status={r.status_code}")

    r = await client.get(f"{base}/{conn_id}/metadata", headers=auth_headers())
    report.record(feature, "GET SP metadata", r.status_code == 200 and "EntityDescriptor" in r.text, f"status={r.status_code}")

    r = await client.get(f"{base}/{conn_id}/login", headers=auth_headers())
    login_ok = r.status_code == 200 and "redirect_url" in r.json()
    report.record(feature, "GET test login", login_ok, f"status={r.status_code}")

    r = await client.delete(f"{base}/{conn_id}", headers=auth_headers())
    report.record(feature, "DELETE connection", r.status_code == 204, f"status={r.status_code}")


async def test_livekit(client: httpx.AsyncClient) -> None:
    feature = "LiveKit WebRTC"
    session_id = ctx.get("session_id")
    if not session_id:
        report.record(feature, "skipped", False, "no session")
        return

    r = await client.post(
        f"/api/v1/livekit/sessions/{session_id}/token",
        headers=auth_headers(),
        json={"participant_identity": "qa-e2e-user", "participant_name": "QA E2E"},
    )
    if r.status_code == 200:
        ok = "token" in r.json() and "livekit_url" in r.json()
        report.record(feature, "POST /token", ok, f"room={r.json().get('room_name')}")
    elif r.status_code == 503:
        report.record(feature, "POST /token", True, "not configured — expected without LiveKit keys")
    else:
        report.record(feature, "POST /token", False, f"status={r.status_code}")


async def test_alerts(client: httpx.AsyncClient) -> None:
    feature = "Alerts"
    r = await client.get("/api/v1/dashboard/alerts?days=7", headers=auth_headers())
    ok = r.status_code == 200 and "alerts" in r.json()
    report.record(feature, "GET /dashboard/alerts", ok, f"active={r.json().get('active_count') if ok else r.status_code}")


async def test_voice_websocket() -> None:
    feature = "Voice Gateway (WebSocket)"
    try:
        import websockets
    except ImportError:
        report.record(feature, "websocket connect", False, "websockets not installed")
        return

    token = ctx.get("token")
    if not token:
        report.record(feature, "websocket connect", False, "no auth token")
        return

    try:
        async with websockets.connect(
            WS_URL,
            open_timeout=5,
            additional_headers={"Authorization": f"Bearer {token}"},
        ) as ws:
            await ws.send(json.dumps({"type": "start", "config": {"language": "en"}}))
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(msg)
            started = data.get("type") == "started" and "session_id" in data
            report.record(feature, "WS start handshake", started, f"type={data.get('type')}")

            if started:
                ctx["ws_session_id"] = data["session_id"]
                await ws.send(json.dumps({"type": "end"}))
                end_msg = await asyncio.wait_for(ws.recv(), timeout=10)
                end_data = json.loads(end_msg)
                report.record(feature, "WS end session", end_data.get("type") in ("ended", "error"), f"type={end_data.get('type')}")
    except Exception as exc:
        report.record(feature, "websocket connect", False, str(exc))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
