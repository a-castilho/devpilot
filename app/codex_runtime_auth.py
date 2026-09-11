from __future__ import annotations

import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ProviderCredential
from app.services import executor
from app.services.vault import Vault

_ORIGINAL_RUN = executor.run


def _openai_api_key() -> str:
    with SessionLocal() as db:
        credentials = list(
            db.scalars(
                select(ProviderCredential)
                .where(
                    ProviderCredential.provider == "openai",
                    ProviderCredential.enabled.is_(True),
                )
                .order_by(ProviderCredential.created_at.desc())
            ).all()
        )
        for credential in credentials:
            try:
                secret = Vault().decrypt(credential.encrypted_secret).strip()
            except ValueError:
                continue
            if secret:
                return secret
    return ""


def _apply_key(environment: dict[str, str], secret: str) -> None:
    # Current Codex builds accept OPENAI_API_KEY for API-key auth. CODEX_API_KEY
    # is also supported by Codex automation paths; setting both avoids auth-mode
    # ambiguity without persisting an auth.json file in the ephemeral container.
    environment["OPENAI_API_KEY"] = secret
    environment["CODEX_API_KEY"] = secret


def refresh_process_environment() -> bool:
    """Expose the active OpenAI key only to this process and its Codex children."""
    secret = _openai_api_key()
    if not secret:
        return False
    _apply_key(os.environ, secret)
    return True


def _run_with_codex_auth(args, cwd=None, timeout=900, env_overrides=None):
    command = str(args[0] if args else "").rsplit("/", 1)[-1]
    if command != "codex":
        return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=env_overrides)

    environment = dict(env_overrides or {})
    if not environment.get("OPENAI_API_KEY") or not environment.get("CODEX_API_KEY"):
        secret = _openai_api_key()
        if secret:
            _apply_key(environment, secret)
            _apply_key(os.environ, secret)
    return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=environment)


def install() -> None:
    refresh_process_environment()
    if getattr(executor.run, "_devpilot_codex_auth", False):
        return
    _run_with_codex_auth._devpilot_codex_auth = True
    executor.run = _run_with_codex_auth


install()
