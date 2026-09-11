from __future__ import annotations

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


def _run_with_codex_auth(args, cwd=None, timeout=900, env_overrides=None):
    command = str(args[0] if args else "").rsplit("/", 1)[-1]
    if command != "codex":
        return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=env_overrides)

    environment = dict(env_overrides or {})
    if not environment.get("OPENAI_API_KEY"):
        secret = _openai_api_key()
        if secret:
            environment["OPENAI_API_KEY"] = secret
    return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=environment)


def install() -> None:
    if getattr(executor.run, "_devpilot_codex_auth", False):
        return
    _run_with_codex_auth._devpilot_codex_auth = True
    executor.run = _run_with_codex_auth


install()
