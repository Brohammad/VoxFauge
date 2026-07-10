"""Locust load test scaffolding for VoxForge (mock providers, no external APIs).

Run:
    pip install locust
    locust -f scripts/load/locustfile.py --host http://127.0.0.1:8000

Headless smoke:
    locust -f scripts/load/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 10 -r 2 -t 30s --csv=load-results
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task


class VoxForgeUser(HttpUser):
    wait_time = between(0.5, 2.0)
    token: str | None = None
    session_id: str | None = None

    def on_start(self) -> None:
        if os.getenv("VOXFORGE_LOAD_TOKEN"):
            self.token = os.environ["VOXFORGE_LOAD_TOKEN"]
            return
        email = f"load-{uuid.uuid4().hex[:8]}@example.com"
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "securepass123",
                "full_name": "Load Test",
                "org_name": "Load Org",
            },
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self.token = resp.json()["tokens"]["access_token"]
            else:
                resp.failure(f"register failed: {resp.status_code}")

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def health(self) -> None:
        self.client.get("/api/v1/health")

    @task(2)
    def create_session(self) -> None:
        with self.client.post(
            "/api/v1/sessions",
            json={},
            headers=self.auth_headers,
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self.session_id = resp.json()["session_id"]

    @task(2)
    def dashboard_outcomes(self) -> None:
        self.client.get("/api/v1/dashboard/outcomes", headers=self.auth_headers)

    @task(1)
    def knowledge_search(self) -> None:
        self.client.post(
            "/api/v1/knowledge/search",
            json={"query": "refund policy", "limit": 3, "min_similarity": 0.0},
            headers=self.auth_headers,
        )

    @task(1)
    def session_replay(self) -> None:
        if not self.session_id:
            return
        self.client.get(
            f"/api/v1/sessions/{self.session_id}/replay",
            headers=self.auth_headers,
        )
