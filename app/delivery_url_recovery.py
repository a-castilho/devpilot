from __future__ import annotations

import json
import re
import threading
import time
from urllib.parse import quote, urlparse

import httpx
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.db import SessionLocal
from app.delivery_cloud_bridge import install_delivery_cloud_bridge
from app.models import AuditEvent, Project
from app.services.audit import record
from app.services.delivery_product_guard import install_delivery_product_guard


_RECOVERABLE_STATUSES = {"blocked", "failed", "deploying", "provisioning", "repairing"}
_RECONCILE_STATUSES = {"repairing", "provisioning", "deploying"}
_ALLOWED_PUBLIC_SUFFIXES = (".vercel.app", ".onrender.com")
_REPO_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GENERIC_DELIVERY_ERROR = "Não foi possível concluir esta etapa. Tente novamente."
_ORIGINAL_RUN_DELIVERY = delivery.run_delivery
_RECONCILER_STARTED = False
_RECONCILER_LOCK = threading.Lock()


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


def _safe_failure_detail(value: object) -> str:
    """Expose only the bounded provider/status message already written by delivery.run_delivery."""
    return " ".join(str(value or "").split())[:180]


def _latest_delivery_failure_error(db: Session, project: Project) -> str:
    event = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.project_id == project.id,
            AuditEvent.action == "project.delivery_failed",
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    if not event:
        return ""
    try:
        details = json.loads(event.details or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(details, dict):
        return ""
    return _safe_failure_detail(details.get("error"))


def _surface_delivery_failure(db: Session, project: Project, state: dict) -> dict:
    if str(state.get("status") or "").lower() != "failed":
        return state
    current = str(state.get("last_error") or "").strip()
    if current and current != _GENERIC_DELIVERY_ERROR:
        return state
    detail = _latest_delivery_failure_error(db, project)
    if not detail:
        return state
    state["last_error"] = f"Falha técnica: {detail}"
    delivery.save_delivery(db, project, state)
    return state


def _github_status_urls(repo_full_name: str, branch: str) -> list[str]:
    if not _REPO_FULL_NAME_RE.fullmatch(repo_full_name):
        return []
    ref = quote(branch or "main", safe="")
    try:
        with httpx.Client(timeout=7.0, follow_redirects=True) as client:
            response = client.get(
                f"https://api.github.com/repos/{repo_full_name}/commits/{ref}/status",
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "DevPilot/1.0",
                },
            )
    except httpx.HTTPError:
        return []
    if response.status_code != 200:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    statuses = payload.get("statuses") if isinstance(payload, dict) else None
    if not isinstance(statuses, list):
        return []

    urls: list[str] = []
    for item in statuses:
        if not isinstance(item, dict) or str(item.get("state") or "").lower() != "success":
            continue
        context = str(item.get("context") or "").lower()
        if "deploy" not in context and "vercel" not in context and "render" not in context:
            continue
        value = _safe_public_url(item.get("target_url"))
        if value and value not in urls:
            urls.append(value)
    return urls


def _candidate_urls(db: Session, project: Project, state: dict) -> list[str]:
    """Return only public URLs with project-specific delivery provenance.

    Never synthesize a deployment URL from the repository/project slug. A readable
    ``<name>.vercel.app`` hostname can belong to a different Vercel project, so an
    HTTP 2xx alone is not sufficient proof that the build-game mission owns it.
    """
    candidates: list[str] = []

    providers = state.get("providers") if isinstance(state.get("providers"), dict) else {}
    for provider in ("vercel", "render"):
        item = providers.get(provider) if isinstance(providers, dict) else None
        if isinstance(item, dict):
            value = _safe_public_url(item.get("url"))
            if value and value not in candidates:
                candidates.append(value)

    repo_full_name = delivery.repository_full_name(db, project)
    for value in _github_status_urls(repo_full_name, project.default_branch or "main"):
        if value not in candidates:
            candidates.append(value)

    return candidates


def _trusted_state_url(db: Session, project: Project, state: dict) -> str:
    """Return the current state URL only when another project-owned source confirms it."""
    current = _safe_public_url(state.get("url"))
    if not current:
        return ""
    return current if current in _candidate_urls(db, project, state) else ""


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
    previous_status = str(state.get("status") or "").lower()
    previous_url = _safe_public_url(state.get("url"))

    for url in _candidate_urls(db, project, state):
        ok, status_code = _probe_public_url(url)
        if not ok:
            continue

        changed = previous_status != "ready" or previous_url != url or state.get("delivery_gate") != "delivered"
        state["status"] = "ready"
        state["url"] = url
        state["last_error"] = ""
        state["blocked_providers"] = []
        state["delivery_mode"] = "external_public_url"
        state["delivery_gate"] = "delivered"
        state["checks"] = [
            {
                "name": "public_url",
                "ok": True,
                "status_code": status_code,
                "url": url,
            }
        ]
        delivery.save_delivery(db, project, state)
        if changed:
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


def _mark_waiting_for_testable_url(
    db: Session,
    project: Project,
    actor: str,
    state: dict,
) -> dict:
    previous_status = str(state.get("status") or "").lower()
    previous_url = _safe_public_url(state.get("url"))

    if previous_status == "ready" or previous_url:
        state["status"] = "deploying"
        state["last_candidate_url"] = previous_url
        state["url"] = ""
    state["delivery_gate"] = "waiting_for_testable_url"
    state["last_error"] = (
        "A missão ainda não terminou: a URL pública precisa responder com sucesso antes da conclusão."
    )
    delivery.save_delivery(db, project, state)
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=actor,
        action="project.delivery_url_not_testable",
        outcome="pending",
        details={"previous_status": previous_status, "candidate_url": previous_url},
    )
    db.commit()
    return state


def _run_delivery_with_public_url_recovery(
    db: Session,
    project: Project,
    actor: str,
) -> dict:
    state = _ORIGINAL_RUN_DELIVERY(db, project, actor)
    state = _surface_delivery_failure(db, project, state)
    status = str(state.get("status") or "").lower()

    # A product repair is an active internal state. It must never be bypassed by
    # scavenging an old deployment URL from provider metadata.
    if status == "repairing":
        return state

    if status in _RECOVERABLE_STATUSES:
        return _recover_public_url(db, project, actor, state)

    if status == "ready":
        url = _trusted_state_url(db, project, state)
        if url:
            ok, _ = _probe_public_url(url)
            if ok:
                state["delivery_gate"] = "delivered"
                delivery.save_delivery(db, project, state)
                return state
        return _mark_waiting_for_testable_url(db, project, actor, state)

    return state


def _reconcile_once() -> int:
    processed = 0
    with SessionLocal() as db:
        projects = list(db.scalars(select(Project).order_by(Project.updated_at.desc()).limit(200)).all())
        for project in projects:
            state = delivery.initial_delivery(project)
            status = str(state.get("status") or "").lower()
            if status not in _RECONCILE_STATUSES or state.get("delivery_gate") == "delivered":
                continue
            try:
                delivery.run_delivery(db, project, "delivery-reconciler")
                processed += 1
            except Exception as error:
                db.rollback()
                print(
                    f"[delivery-reconciler] project={project.id} status={status} error={type(error).__name__}: {str(error)[:180]}",
                    flush=True,
                )
    return processed


def _reconciler_loop() -> None:
    # Give application startup/migrations time to settle, then continue delivery
    # independently from any browser session. The worker executes repair tasks; this
    # loop re-proves the remote product and advances cloud publication afterwards.
    time.sleep(4)
    while True:
        try:
            processed = _reconcile_once()
            if processed:
                print(f"[delivery-reconciler] processed={processed}", flush=True)
        except Exception as error:
            print(
                f"[delivery-reconciler] cycle error={type(error).__name__}: {str(error)[:180]}",
                flush=True,
            )
        time.sleep(8)


def _start_reconciler() -> None:
    global _RECONCILER_STARTED
    with _RECONCILER_LOCK:
        if _RECONCILER_STARTED:
            return
        _RECONCILER_STARTED = True
        threading.Thread(
            target=_reconciler_loop,
            name="devpilot-delivery-reconciler",
            daemon=True,
        ).start()


@delivery.router.post("/projects/{project_id}/delivery/validate-url")
def validate_delivery_url(
    project_id: str,
    db: Session = Depends(delivery.get_db),
    actor: str = Depends(delivery.require_access),
):
    """Revalidate the final game reward against a real, reachable public URL.

    A completed build-game task is not enough to finish the mission. The delivery gate only
    becomes ``delivered`` when DevPilot can perform a real HTTP request to a public Vercel or
    Render URL and receive a successful/redirect response.
    """
    project = delivery.project_or_404(db, project_id)
    state = delivery.initial_delivery(project)
    if str(state.get("status") or "").lower() == "repairing":
        return state

    recovered = _recover_public_url(db, project, actor, state)
    if str(recovered.get("status") or "").lower() == "ready" and _safe_public_url(recovered.get("url")):
        return recovered

    if str(state.get("status") or "").lower() == "ready" or _safe_public_url(state.get("url")):
        return _mark_waiting_for_testable_url(db, project, actor, state)

    if state.get("delivery_gate") != "waiting_for_testable_url":
        state["delivery_gate"] = "waiting_for_testable_url"
        delivery.save_delivery(db, project, state)
    return state


def install_delivery_url_recovery() -> None:
    """Recover a real test URL and reuse clouds configured by Super Admin.

    Managed Neon/Render/Vercel credentials remain the primary delivery path. Before cloud
    provisioning, the product guard proves that the requested system is actually materialized
    on the remote default branch and starts an autonomous repair task when it is not. Only after
    that proof may the public URL recovery/gate mark the mission as delivered.
    """
    install_delivery_cloud_bridge()
    install_delivery_product_guard()
    current = delivery.run_delivery
    if getattr(current, "_devpilot_public_url_recovery", False):
        _start_reconciler()
        return
    global _ORIGINAL_RUN_DELIVERY
    _ORIGINAL_RUN_DELIVERY = current
    setattr(_run_delivery_with_public_url_recovery, "_devpilot_public_url_recovery", True)
    delivery.run_delivery = _run_delivery_with_public_url_recovery
    _start_reconciler()
