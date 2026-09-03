from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.config import get_settings
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault


_CLOUD_ADMIN_LABEL = "cloud-admin"
_CLOUD_ADMIN_PREFIX = "cloud:"
_ORIGINAL_CONNECTION = delivery.connection
_ORIGINAL_REQUEST_JSON = delivery.request_json
_ORIGINAL_SELECTED_PROVIDERS = delivery.selected_providers
_ORIGINAL_VERIFY = delivery.verify
_ORIGINAL_PROVISION_VERCEL = delivery.provision_vercel


def _cloud_admin_row(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{_CLOUD_ADMIN_PREFIX}{provider.strip().lower()}",
            ProviderCredential.label == _CLOUD_ADMIN_LABEL,
        )
    )


def cloud_admin_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Read a credential managed by Super Admin > Clouds without exposing it to the browser."""
    item = _cloud_admin_row(db, workspace_id, provider)
    if not item or not item.enabled:
        return None

    try:
        token = Vault().decrypt(item.encrypted_secret).strip()
    except (TypeError, ValueError):
        return None
    if not token:
        return None

    try:
        metadata = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return token, str(metadata.get("scope") or "").strip()


def managed_trial_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Use DevPilot's platform credential for an unconfigured trial workspace."""
    settings = get_settings()
    normalized = provider.strip().lower()
    if not settings.managed_trial_clouds_enabled:
        return None
    if normalized not in settings.managed_trial_providers:
        return None
    if _cloud_admin_row(db, workspace_id, normalized) is not None:
        return None

    platform = db.scalar(
        select(Workspace).where(Workspace.slug == settings.managed_trial_workspace_slug)
    )
    if not platform or platform.id == workspace_id:
        return None
    return cloud_admin_connection(db, platform.id, normalized)


def _connection_with_cloud_admin(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    current = cloud_admin_connection(db, workspace_id, provider)
    if current is not None:
        return current

    legacy = _ORIGINAL_CONNECTION(db, workspace_id, provider)
    if legacy is not None:
        return legacy

    return managed_trial_connection(db, workspace_id, provider)


def _normalize_render_repository(value: object) -> str:
    """Return a canonical GitHub HTTPS URL accepted by Render's repo field."""
    candidate = str(value or "").strip().rstrip("/")
    if not candidate:
        return ""

    if candidate.startswith("git@github.com:"):
        path = candidate.split(":", 1)[1].strip("/").removesuffix(".git")
        return f"https://github.com/{path}" if path else ""

    marker = "github.com/"
    if marker in candidate:
        path = candidate.split(marker, 1)[1].strip("/").removesuffix(".git")
        return f"https://github.com/{path}" if path else ""

    return candidate.removesuffix(".git")


def _request_json_with_cloud_scope(
    client,
    provider: str,
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    params: dict[str, Any] | None = None,
):
    normalized = dict(params) if isinstance(params, dict) else params
    normalized_payload = dict(payload) if isinstance(payload, dict) else payload

    if provider == "vercel" and isinstance(normalized, dict):
        scope = str(normalized.get("teamId") or "").strip()
        if scope and not scope.startswith("team_"):
            normalized.pop("teamId", None)
            normalized["slug"] = scope

    if provider == "render" and isinstance(normalized_payload, dict) and "repo" in normalized_payload:
        normalized_payload["repo"] = _normalize_render_repository(normalized_payload.get("repo"))

    return _ORIGINAL_REQUEST_JSON(
        client,
        provider,
        method,
        url,
        token,
        payload=normalized_payload,
        params=normalized,
    )


def _values(blueprint: dict[str, Any], key: str) -> set[str]:
    raw = blueprint.get(key) or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {str(value).strip().lower() for value in raw if str(value).strip()}


def _adaptive_selected_providers(project) -> list[str]:
    """Deploy only the infrastructure the project blueprint actually requires."""
    config = delivery.config_for(project)
    blueprint = config.get("project_blueprint")
    if not isinstance(blueprint, dict):
        return _ORIGINAL_SELECTED_PROVIDERS(project)

    databases = _values(blueprint, "databases")
    backend = _values(blueprint, "backend")
    frontend = _values(blueprint, "frontend")
    project_types = _values(blueprint, "project_type")

    selected: list[str] = []
    if databases.intersection({"postgres", "postgresql", "neon"}):
        selected.append("neon")
    if backend and not backend.issubset({"none", "nenhum", "static", "estatico", "estático"}):
        selected.append("render")
    if frontend and not frontend.issubset({"none", "nenhum"}):
        selected.append("vercel")

    if selected:
        return selected

    if project_types.intersection({"site", "website", "landing-page", "landing", "frontend", "static"}):
        return ["vercel"]
    if project_types.intersection({"api", "backend", "service", "microservice", "worker"}):
        return ["render"]

    return _ORIGINAL_SELECTED_PROVIDERS(project)


def _probe(url: str) -> tuple[bool, int]:
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            response = client.get(url, headers={"Accept": "application/json,text/html,*/*"})
    except httpx.HTTPError:
        return False, 0
    return 200 <= response.status_code < 400, response.status_code


def _gated_provision_vercel(
    client,
    token: str,
    account_id: str,
    project,
    state: dict[str, Any],
    backend_url: str | None,
    repo_full_name: str,
) -> str:
    """Do not build the frontend until the required Render backend is reachable."""
    requested = {str(item).strip().lower() for item in (state.get("requested") or []) if item}
    providers = state.setdefault("providers", {})
    render = providers.setdefault("render", {}) if "render" in requested else {}
    effective_backend_url = str(backend_url or render.get("url") or "").rstrip("/")

    if "render" in requested:
        health_url = f"{effective_backend_url}/health" if effective_backend_url else ""
        ready, status_code = _probe(health_url) if health_url else (False, 0)
        render["status"] = "ready" if ready else "deploying"
        render["health_status_code"] = status_code
        render["health_url"] = health_url
        if not ready:
            vercel = providers.setdefault("vercel", {})
            vercel["status"] = "waiting_backend"
            state["status"] = "deploying"
            state["waiting_for"] = "render_ready"
            return str(vercel.get("url") or "")

    vercel = providers.setdefault("vercel", {})
    configured_backend = str(vercel.get("backend_url") or "").rstrip("/")
    if effective_backend_url and configured_backend != effective_backend_url:
        # Recover old/partial deployments: env must be written before the build that consumes it.
        vercel["backend_configured"] = False
        vercel["deployment_id"] = ""
        vercel["url"] = ""

    result = _ORIGINAL_PROVISION_VERCEL(
        client,
        token,
        account_id,
        project,
        state,
        effective_backend_url or None,
        repo_full_name,
    )
    if effective_backend_url and vercel.get("backend_configured"):
        vercel["backend_url"] = effective_backend_url
    state.pop("waiting_for", None)
    return result


def _adaptive_verify(state: dict[str, Any]) -> dict[str, Any]:
    """Verify only requested components; database proof comes from Neon provisioning, not Vercel /health."""
    providers = state.get("providers") if isinstance(state.get("providers"), dict) else {}
    requested = [str(item).lower() for item in (state.get("requested") or []) if item]
    if not requested:
        requested = [name for name in ("neon", "render", "vercel") if isinstance(providers.get(name), dict)]

    checks: list[dict[str, Any]] = []
    public_url = ""

    if "neon" in requested:
        neon = providers.get("neon") if isinstance(providers.get("neon"), dict) else {}
        ok = bool(neon.get("project_id") and neon.get("homolog_branch_id") and neon.get("status") == "ready")
        checks.append({"name": "database", "provider": "neon", "ok": ok, "status_code": 200 if ok else 0, "url": ""})

    if "render" in requested:
        render = providers.get("render") if isinstance(providers.get("render"), dict) else {}
        render_url = str(render.get("url") or "").rstrip("/")
        ok, status_code = _probe(f"{render_url}/health") if render_url else (False, 0)
        render["status"] = "ready" if ok else "deploying"
        render["health_status_code"] = status_code
        checks.append({"name": "backend", "provider": "render", "ok": ok, "status_code": status_code, "url": f"{render_url}/health" if render_url else ""})
        if render_url:
            public_url = render_url

    if "vercel" in requested:
        vercel = providers.get("vercel") if isinstance(providers.get("vercel"), dict) else {}
        vercel_url = str(vercel.get("url") or "").rstrip("/")
        ok, status_code = _probe(vercel_url) if vercel_url else (False, 0)
        checks.append({"name": "frontend", "provider": "vercel", "ok": ok, "status_code": status_code, "url": vercel_url})
        if vercel_url:
            public_url = vercel_url

    ready = bool(requested) and all(item["ok"] for item in checks) and len(checks) == len(requested)
    return {
        "status": "ready" if ready else "deploying",
        "url": public_url,
        "checks": checks,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


@delivery.router.post("/projects/{project_id}/delivery/auto")
def automatic_delivery(
    project_id: str,
    db: Session = delivery.Depends(delivery.get_db),
    actor: str = delivery.Depends(delivery.require_access),
):
    """Continue the idempotent delivery state machine for an authenticated project user."""
    project = delivery.project_or_404(db, project_id)
    return delivery.run_delivery(db, project, actor)


def install_delivery_cloud_bridge() -> None:
    """Use system cloud credentials and adapt final delivery to the real project architecture."""
    if not getattr(delivery.connection, "_devpilot_cloud_admin_bridge", False):
        setattr(_connection_with_cloud_admin, "_devpilot_cloud_admin_bridge", True)
        delivery.connection = _connection_with_cloud_admin
    if not getattr(delivery.request_json, "_devpilot_cloud_scope_bridge", False):
        setattr(_request_json_with_cloud_scope, "_devpilot_cloud_scope_bridge", True)
        delivery.request_json = _request_json_with_cloud_scope
    if not getattr(delivery.selected_providers, "_devpilot_adaptive_delivery", False):
        setattr(_adaptive_selected_providers, "_devpilot_adaptive_delivery", True)
        delivery.selected_providers = _adaptive_selected_providers
    if not getattr(delivery.provision_vercel, "_devpilot_render_ready_gate", False):
        setattr(_gated_provision_vercel, "_devpilot_render_ready_gate", True)
        delivery.provision_vercel = _gated_provision_vercel
    if not getattr(delivery.verify, "_devpilot_adaptive_verify", False):
        setattr(_adaptive_verify, "_devpilot_adaptive_verify", True)
        delivery.verify = _adaptive_verify
