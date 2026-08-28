from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


class LinkedInOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkedInToken:
    access_token: str
    refresh_token: str
    scopes: str
    expires_at: datetime | None


def oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.linkedin_client_id and settings.linkedin_client_secret)


def _state_secret() -> bytes:
    settings = get_settings()
    secret = settings.auth_secret or settings.bootstrap_token
    return secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_oauth_state(*, workspace_id: str, user_id: str) -> str:
    settings = get_settings()
    payload = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "exp": int(time.time()) + settings.linkedin_oauth_state_ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64encode(raw)
    signature = hmac.new(_state_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def verify_oauth_state(state: str) -> dict[str, Any]:
    try:
        body, signature = state.split(".", 1)
    except ValueError as error:
        raise LinkedInOAuthError("OAuth state inválido") from error
    expected = hmac.new(_state_secret(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64decode(signature)
    except Exception as error:
        raise LinkedInOAuthError("OAuth state inválido") from error
    if not hmac.compare_digest(expected, supplied):
        raise LinkedInOAuthError("OAuth state inválido")
    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError) as error:
        raise LinkedInOAuthError("OAuth state inválido") from error
    if int(payload.get("exp", 0)) < int(time.time()):
        raise LinkedInOAuthError("OAuth state expirado. Inicie a conexão novamente")
    if not payload.get("workspace_id") or not payload.get("user_id"):
        raise LinkedInOAuthError("OAuth state incompleto")
    return payload


def authorization_url(*, workspace_id: str, user_id: str, redirect_uri: str) -> str:
    settings = get_settings()
    if not oauth_configured():
        raise LinkedInOAuthError("LinkedIn OAuth não configurado no servidor")
    scopes = " ".join(sorted(settings.linkedin_scope_set))
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.linkedin_client_id,
            "redirect_uri": redirect_uri,
            "state": create_oauth_state(workspace_id=workspace_id, user_id=user_id),
            "scope": scopes,
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


async def exchange_code(*, code: str, redirect_uri: str) -> LinkedInToken:
    settings = get_settings()
    if not oauth_configured():
        raise LinkedInOAuthError("LinkedIn OAuth não configurado no servidor")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise LinkedInOAuthError(f"LinkedIn recusou a troca OAuth ({response.status_code})")
    payload = response.json()
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise LinkedInOAuthError("LinkedIn não retornou access_token")
    expires_in = int(payload.get("expires_in") or 0)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        if expires_in > 0
        else None
    )
    return LinkedInToken(
        access_token=access_token,
        refresh_token=str(payload.get("refresh_token") or ""),
        scopes=str(payload.get("scope") or " ".join(sorted(settings.linkedin_scope_set))),
        expires_at=expires_at,
    )


async def fetch_userinfo(access_token: str) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
    if response.status_code >= 400:
        raise LinkedInOAuthError(f"LinkedIn userinfo falhou ({response.status_code})")
    payload = response.json()
    return {
        "member_id": str(payload.get("sub") or ""),
        "display_name": str(payload.get("name") or ""),
        "email": str(payload.get("email") or ""),
    }


def connection_capabilities(scopes: str) -> dict[str, Any]:
    scope_set = {item for item in scopes.replace(",", " ").split() if item}
    return {
        "oauth_connected": True,
        "identity_read": "openid" in scope_set or "profile" in scope_set,
        "profile_write": False,
        "profile_write_reason": (
            "A conexão OAuth está ativa, mas edição de headline/about/experiências exige "
            "produto e permissões de escrita aprovados pelo LinkedIn. O DevPilot não simula "
            "cliques nem envia payload para endpoints não autorizados."
        ),
    }
