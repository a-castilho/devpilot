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
from fastapi import Depends, Header, HTTPException

from app.config import get_settings


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


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
        "role": str(user.role),
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
        role = Role(payload["role"])
        user_id = str(payload["sub"])
        workspace_id = str(payload["workspace_id"])
        email = str(payload["email"])
    except HTTPException:
        raise
    except (binascii.Error, KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from error
    return Principal(
        user_id=user_id,
        workspace_id=workspace_id,
        email=email,
        role=role,
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    return token


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    token = _bearer_token(authorization)
    bootstrap = get_settings().bootstrap_token
    if bootstrap and hmac.compare_digest(token, bootstrap):
        return Principal(
            user_id=None,
            workspace_id=None,
            email=None,
            role=Role.ADMIN,
            bootstrap=True,
        )
    return decode_access_token(token)


def require_access(principal: Principal = Depends(current_principal)) -> str:
    return principal.actor


def require_super_admin(principal: Principal = Depends(current_principal)) -> str:
    if principal.role is not Role.ADMIN:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return principal.actor


def require_bootstrap_access(authorization: str | None = Header(default=None)) -> str:
    token = _bearer_token(authorization)
    expected = get_settings().bootstrap_token
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bootstrap token")
    return "owner"


def privacy_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]
