import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from voxforge.config import Settings
from voxforge.core.domain.auth import OrgRole, Principal, PrincipalType
from voxforge.core.exceptions import UnauthorizedError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


def generate_api_key(prefix: str, pepper: str) -> tuple[str, str, str]:
    """Return (raw_key, key_prefix, key_hash)."""
    raw_suffix = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{raw_suffix}"
    key_prefix = raw_key[:12]
    return raw_key, key_prefix, hash_api_key(raw_key, pepper)


def hash_api_key(raw_key: str, pepper: str) -> str:
    return hashlib.sha256(f"{pepper}{raw_key}".encode()).hexdigest()


def create_access_token(
    *,
    user_id: UUID,
    org_id: UUID,
    role: OrgRole,
    settings: Settings,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role.value,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, user_id: UUID, org_id: UUID, settings: Settings) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc


def principal_from_access_token(token: str, settings: Settings) -> Principal:
    payload = decode_token(token, settings)
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")
    return Principal(
        type=PrincipalType.USER,
        user_id=UUID(payload["sub"]),
        org_id=UUID(payload["org_id"]),
        role=OrgRole(payload["role"]),
    )


def principal_from_api_key_record(
    *,
    api_key_id: UUID,
    org_id: UUID,
    scopes: list[str],
) -> Principal:
    return Principal(
        type=PrincipalType.API_KEY,
        org_id=org_id,
        scopes=scopes,
        api_key_id=api_key_id,
    )
