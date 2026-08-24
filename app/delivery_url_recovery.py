from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.models import Project
from app.services.audit import record


_RECOVERABLE_STATUSES = {"blocked", "failed", "deploying", "provisioning"}
_ALLOWED_PUBLIC_SUFFIXES = (".vercel.app", ".onrender.com")
_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_ORIGINAL_RUN_DELIVERY = delivery.run_delivery


def _safe_public_url(value: object) -> str:
    candidate = str(value or "").strip().rstrip("/")
    if not candidate:
        return ""
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(_ALLOWED_PUBLIC_SUFFIXES):
        return ""
    return candidate


def _candidate_urls(db: Session, project: Project, state: dict) -> list[str]:
    candidates: list[str] = []

    current = _safe_public_url(state.get("url"))
    if current:
        candidates.append(current)

    providers = state.get("providers") if isinstance(state.get("providers"), dict) else {}
    for provider in ("vercel", "render"):
        item = providers.get(provider) if isinstance(providers, dict) else None
        if isinstance(item, dict):
            value = _safe_public_url(item.get("url"))
            if value and value not in candidates:
                candidates.append(value)

    repo_full_name = delivery.repository_full_name(db, project)
    repo_name = repo_full_name.rsplit("/", 1)[-1].removesuffix(".git").strip()
    if repo_name and _REPO_NAME_RE.fullmatch(repo_name):
        value = f"https://{repo_name.lower()}.vercel.app"
        if value not in candidates:
            candidates.append(value)

    return candidates


def _probe_public_url(url: str) -> tuple[bool, int]:
    try:
        with httpx.Client(timeout=7.0, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={"Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
            )
    except httpx.HTTPError:
        return False, 0
    return 200 <= response.status_code < 400, response.status_code


def _recover_public_url(db: Session, project: Project, actor: str, state: dict) -> dict:
    for url in _candidate_urls(db, project, state):
        ok, status_code = _probe_public_url(url)
        if not ok:
            continue

        state["status"] = "ready"
        state["url"] = url
        state["last_error"] = ""
        state["blocked_providers"] = []
        state["delivery_mode"] = "external_public_url"
        state["checks"] = [
            {
                "name": "frontend",
                "ok": True,
                "status_code": status_code,
                "url": url,
            }
        ]
        delivery.save_delivery(db, project, state)
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor=actor,
            action="project.delivery_public_url_recovered",
            outcome="success",
            details={"url": url, "status_code": status_code},
        )
        db.commit()
        return state
    return state


def _run_delivery_with_public_url_recovery(
    db: Session,
    project: Project,
    actor: str,
) -> dict:
    state = _ORIGINAL_RUN_DELIVERY(db, project, actor)
    status = str(state.get("status") or "").lower()
    if status in _RECOVERABLE_STATUSES:
        return _recover_public_url(db, project, actor, state)
    return state


def install_delivery_url_recovery() -> None:
    """Allow the game reward to recover an already-published URL without cloud secrets.

    DevPilot still uses its managed Neon/Render/Vercel credentials when configured. If those
    credentials are missing, a public deployment created by the project's own CI/CD can be
    detected safely by its canonical Vercel repository URL and returned as the game reward.
    """
    current = delivery.run_delivery
    if getattr(current, "_devpilot_public_url_recovery", False):
        return
    setattr(_run_delivery_with_public_url_recovery, "_devpilot_public_url_recovery", True)
    delivery.run_delivery = _run_delivery_with_public_url_recovery
