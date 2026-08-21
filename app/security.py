from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


MANAGEMENT_ROLES = {Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def canonical_role(value: str | Role) -> Role:
    if isinstance(value, Role):
        return value
    raw = str(value).strip()
    legacy = {"admin": Role.SUPER_ADMIN, "user": Role.VIEWER}
    if raw in legacy:
        return legacy[raw]
    try:
        return Role(raw.upper())
    except ValueError as error:
        raise HTTPException(status_code=403, detail="Perfil de acesso inválido") from error


def _analyst_can_write(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path.rstrip("/")
    if method == "POST" and path in {"/api/tasks", "/api/voice/commands"}:
        return True
    if method == "POST" and path.startswith("/api/projects/") and path.endswith("/analyze"):
        return True
    if method == "POST" and path.startswith("/api/tasks/") and path.endswith("/retry"):
        return True
    return False


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    workspace_id: str | None
    email: str | None
    role: Role
    bootstrap: bool = False

    @property
    def actor(self) -> str:
        return "owner" if self.bootstrap else f"user:{self.user_id}"


_ARGON2_MEMORY_KIB = 19 * 1024
_ARGON2_ITERATIONS = 2
_ARGON2_LANES = 1
_ARGON2_LENGTH = 32


def hash_password(password: str) -> str:
    kdf = Argon2id(
        salt=os.urandom(16),
        length=_ARGON2_LENGTH,
        iterations=_ARGON2_ITERATIONS,
        lanes=_ARGON2_LANES,
        memory_cost=_ARGON2_MEMORY_KIB,
    )
    return kdf.derive_phc_encoded(password.encode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        Argon2id.verify_phc_encoded(password.encode("utf-8"), password_hash)
        return True
    except (InvalidKey, TypeError, ValueError):
        return False


_DUMMY_PASSWORD_HASH = hash_password("devpilot-invalid-credential-sentinel")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _auth_secret() -> bytes:
    secret = get_settings().auth_secret.strip()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Autenticação por senha não configurada")
    return secret.encode("utf-8")


def create_access_token(user) -> tuple[str, int]:
    settings = get_settings()
    ttl = max(60, int(settings.auth_token_ttl_seconds))
    now = int(datetime.now(timezone.utc).timestamp())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "workspace_id": str(user.workspace_id),
        "email": user.email,
        "role": canonical_role(user.role).value,
        "iat": now,
        "exp": now + ttl,
    }
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signed = f"{encoded_header}.{encoded_payload}"
    signature = _b64encode(hmac.new(_auth_secret(), signed.encode(), hashlib.sha256).digest())
    return f"{signed}.{signature}", ttl


def decode_access_token(token: str) -> Principal:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signed = f"{encoded_header}.{encoded_payload}"
        expected = _b64encode(hmac.new(_auth_secret(), signed.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(encoded_signature, expected):
            raise ValueError("signature")
        header = json.loads(_b64decode(encoded_header))
        payload = json.loads(_b64decode(encoded_payload))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("header")
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        role = canonical_role(payload["role"])
        user_id = str(payload["sub"])
        workspace_id = str(payload["workspace_id"])
        email = str(payload["email"])
    except HTTPException:
        raise
    except (binascii.Error, KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from error
    return Principal(user_id=user_id, workspace_id=workspace_id, email=email, role=role)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    return token


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Authenticate normal API requests using only short-lived user access tokens.

    The bootstrap token is intentionally not accepted here. It is reserved exclusively
    for ``POST /api/auth/bootstrap`` through ``require_bootstrap_access``.
    """
    return decode_access_token(_bearer_token(authorization))


def session_principal(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
) -> Principal:
    user = db.scalar(select(User).where(User.id == principal.user_id))
    if not user or not user.active or user.workspace_id != principal.workspace_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    return Principal(
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        role=canonical_role(user.role),
    )


def require_access(
    request: Request,
    principal: Principal = Depends(session_principal),
) -> str:
    if request.method.upper() in _SAFE_METHODS:
        return principal.actor
    if principal.role is Role.VIEWER:
        raise HTTPException(status_code=403, detail="Perfil de leitura não pode executar esta ação")
    if principal.role is Role.ANALYST and not _analyst_can_write(request):
        raise HTTPException(
            status_code=403,
            detail="Perfil de analista não pode administrar configurações ou aprovações",
        )
    return principal.actor


def require_roles(*allowed: Role):
    allowed_set = {canonical_role(role) for role in allowed}

    def dependency(principal: Principal = Depends(session_principal)) -> Principal:
        if principal.role is Role.SUPER_ADMIN:
            return principal
        if principal.role not in allowed_set:
            raise HTTPException(status_code=403, detail="Você não tem permissão para executar esta ação")
        return principal

    return dependency


def require_super_admin(
    principal: Principal = Depends(session_principal),
) -> str:
    """Restrict sensitive platform administration to SUPER_ADMIN only."""
    if principal.role is not Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Acesso exclusivo do Super Admin")
    return principal.actor


def can_manage_role(actor: Role, target: Role) -> bool:
    actor = canonical_role(actor)
    target = canonical_role(target)
    if actor is Role.SUPER_ADMIN:
        return True
    if actor is Role.OWNER:
        return target in {Role.ADMIN, Role.ANALYST, Role.VIEWER}
    if actor is Role.ADMIN:
        return target in {Role.ANALYST, Role.VIEWER}
    return False


def ensure_can_manage_role(actor: Role, target: Role) -> Role:
    target = canonical_role(target)
    if not can_manage_role(canonical_role(actor), target):
        raise HTTPException(status_code=403, detail="Você não pode atribuir este perfil")
    return target


def require_bootstrap_access(authorization: str | None = Header(default=None)) -> str:
    """Validate the one-purpose token used only to create the first persistent admin."""
    token = _bearer_token(authorization)
    expected = get_settings().bootstrap_token
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bootstrap token")
    return "owner"


def privacy_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]
