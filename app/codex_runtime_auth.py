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


def refresh_process_environment() -> bool:
    """Expose the active OpenAI key only to the server process/child Codex process.

    The controlled worker launches Codex directly with subprocess.Popen, so the
    key must be available in the parent environment in addition to executor.run's
    explicit env_overrides path. The secret is never returned, logged or persisted
    outside the existing encrypted Vault row.
    """
    secret = _openai_api_key()
    if not secret:
        return False
    os.environ["OPENAI_API_KEY"] = secret
    return True


def _run_with_codex_auth(args, cwd=None, timeout=900, env_overrides=None):
    command = str(args[0] if args else "").rsplit("/", 1)[-1]
    if command != "codex":
        return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=env_overrides)

    environment = dict(env_overrides or {})
    if not environment.get("OPENAI_API_KEY"):
        secret = _openai_api_key()
        if secret:
            environment["OPENAI_API_KEY"] = secret
            os.environ["OPENAI_API_KEY"] = secret
    return _ORIGINAL_RUN(args, cwd=cwd, timeout=timeout, env_overrides=environment)


def install() -> None:
    # Refresh even when the runner wrapper was already installed so a newly saved
    # key becomes available after application restart without another integration.
    refresh_process_environment()
    if getattr(executor.run, "_devpilot_codex_auth", False):
        return
    _run_with_codex_auth._devpilot_codex_auth = True
    executor.run = _run_with_codex_auth


install()
