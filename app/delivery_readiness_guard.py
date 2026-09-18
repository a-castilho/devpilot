from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app import product_delivery_routes as delivery
from app.db import SessionLocal
from app.github_optional_org import github_credential_candidates
from app.models import Project
from app.services.github_provisioning import GitHubProvisioningError, bootstrap_repository
from app.services.vault import Vault

_GITHUB_API = "https://api.github.com"
_ORIGINAL_RUN_DELIVERY = delivery.run_delivery


def _repository_parts(project: Project) -> tuple[str, str]:
    parsed = urlparse(str(project.repository_url or ""))
    if str(parsed.hostname or "").lower() != "github.com":
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1].removesuffix(".git")


def _github_token(project: Project) -> str:
    with SessionLocal() as db:
        current = db.get(Project, project.id) or project
        for credential in github_credential_candidates(db, current)[:8]:
            try:
                token = Vault().decrypt(credential.encrypted_secret).strip()
            except ValueError:
                continue
            if token:
                return token
    return ""


def _requires_dockerfile(project: Project) -> bool:
    # Render can deploy the managed starter only when a Dockerfile is present.
    # Vercel-only projects must never be blocked by this backend artifact.
    return "render" in delivery.selected_providers(project)


def _published_dockerfile(project: Project) -> tuple[bool, str]:
    # The product guard performs a full remote tree proof immediately before this
    # wrapper. Reuse that stronger proof instead of deadlocking on a second GitHub
    # credential path that can disagree for legacy projects.
    try:
        import json
        config = json.loads(project.codex_config or "{}")
        preflight = (config.get("delivery") or {}).get("repository_preflight") or {}
        if preflight.get("ok") is True:
            return True, "deployable revision proven by remote repository preflight"
    except (TypeError, ValueError):
        pass
    if not _requires_dockerfile(project):
        return True, "Dockerfile not required for selected providers"
    owner, repo = _repository_parts(project)
    if not owner or not repo:
        return True, "non_github_repository"
    token = _github_token(project)
    branch = str(project.default_branch or "main").strip() or "main"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot-Delivery-Readiness/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.get(
            f"{_GITHUB_API}/repos/{owner}/{repo}/contents/Dockerfile",
            params={"ref": branch},
            headers=headers,
            timeout=12.0,
        )
    except httpx.HTTPError:
        return False, "github_readiness_unavailable"
    if response.status_code == 200:
        return True, f"Dockerfile published on {branch}"
    if response.status_code == 404:
        return False, f"Dockerfile not published on {branch}"
    return False, f"github readiness HTTP {response.status_code}"


def _repair_deployable_revision(project: Project) -> tuple[bool, str]:
    """Publish the safe managed starter when delivery is waiting for deployable code.

    bootstrap_repository is idempotent: existing application files are preserved and
    only missing managed starter files are created. This closes the waiting_code loop
    without overwriting code already produced by the project execution pipeline.
    """
    owner, repo = _repository_parts(project)
    if not owner or not repo:
        return False, "non_github_repository"
    token = _github_token(project)
    if not token:
        return False, "github_credential_unavailable"
    branch = str(project.default_branch or "main").strip() or "main"
    try:
        result = bootstrap_repository(
            owner,
            repo,
            token,
            project_name=str(project.name or project.slug or repo),
            description=str(project.description or ""),
            branch=branch,
        )
    except GitHubProvisioningError as error:
        return False, f"starter_repair_failed:{error.status_code}"
    except httpx.HTTPError:
        return False, "starter_repair_unavailable"
    created = result.get("created") if isinstance(result, dict) else []
    return True, f"deployable revision repaired on {branch}; created={len(created or [])}"


def _waiting_state(db, project: Project, proof: str) -> dict:
    state = delivery.initial_delivery(project)
    state["status"] = "waiting_code"
    state["waiting_for"] = "deployable_revision"
    state["last_error"] = ""
    state["readiness"] = {
        "ready": False,
        "proof": proof,
        "required": ["Dockerfile on default branch"] if _requires_dockerfile(project) else [],
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    delivery.save_delivery(db, project, state)
    return state


def run_delivery_when_code_is_ready(db, project: Project, actor: str):
    ready, proof = _published_dockerfile(project)
    # Any GitHub project selected for Render must self-heal its deployable
    # revision. Previously only a literal 404 triggered repair; missing/legacy
    # GitHub credentials left projects in waiting_code forever even though the
    # bootstrap path can resolve the managed credential independently.
    if not ready and _requires_dockerfile(project):
        repaired, repair_proof = _repair_deployable_revision(project)
        if repaired:
            ready, proof = _published_dockerfile(project)
            if not ready:
                proof = f"{repair_proof}; {proof}"
        else:
            proof = f"{proof}; {repair_proof}"
    if not ready:
        return _waiting_state(db, project, proof)

    # A project may have been persisted as waiting_code by an older readiness rule.
    # Once the current provider-aware proof succeeds, clear the stale gate so the
    # cloud state machine can actually reach Vercel/Render on this same pass.
    state = delivery.initial_delivery(project)
    readiness = state.setdefault("readiness", {})
    readiness.update({"ready": True, "proof": proof})
    state.pop("waiting_for", None)
    if str(state.get("status") or "").lower() == "waiting_code":
        state["status"] = "pending"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    delivery.save_delivery(db, project, state)
    return _ORIGINAL_RUN_DELIVERY(db, project, actor)


def install() -> None:
    if getattr(delivery.run_delivery, "_devpilot_readiness_guard", False):
        return
    run_delivery_when_code_is_ready._devpilot_readiness_guard = True
    delivery.run_delivery = run_delivery_when_code_is_ready


install()
