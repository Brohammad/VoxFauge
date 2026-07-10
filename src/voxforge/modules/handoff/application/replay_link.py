"""Signed replay URL generation for handoff packages."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from uuid import UUID

from voxforge.config import Settings


class ReplayLinkService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _signing_secret(self) -> str:
        return self._settings.handoff_replay_signing_secret or self._settings.jwt_secret_key

    def generate(
        self,
        *,
        session_id: UUID,
        org_id: UUID,
        handoff_id: UUID,
    ) -> tuple[str, str]:
        token = secrets.token_urlsafe(24)
        payload = f"{session_id}:{org_id}:{handoff_id}:{token}"
        signature = hmac.new(
            self._signing_secret().encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]
        signed_token = f"{token}.{signature}"
        base = self._settings.public_base_url.rstrip("/") or "http://localhost:8000"
        replay_url = f"{base}/dashboard#replay={session_id}&token={signed_token}"
        return replay_url, signed_token

    def verify(self, *, session_id: UUID, org_id: UUID, handoff_id: UUID, token: str) -> bool:
        if "." not in token:
            return False
        raw, signature = token.rsplit(".", 1)
        payload = f"{session_id}:{org_id}:{handoff_id}:{raw}"
        expected = hmac.new(
            self._signing_secret().encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]
        return hmac.compare_digest(signature, expected)
