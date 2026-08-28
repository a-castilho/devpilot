from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProviderCredential, Repository
from app.services.audit import record
from app.services.vault import Vault


NEON_API = "https://console.neon.tech/api/v2"
RENDER_API = "https://api.render.com/v1"
VERCEL_API = "https://api.vercel.com"
PROVIDERS = ("neon", "render", "vercel")
CURRENT_CREDENTIAL_LABEL = "cloud-admin"
CURRENT_PROVIDER_PREFIX = "cloud:"
LEGACY_CREDENTIAL_LABEL = "Principal"
LEGACY_PROVIDER_PREFIX = "cloud-"
MAX_AUTO_RETRIES = 3
RETRY_DELAYS_SECONDS = (60, 300, 900)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def config_for(project: Project) -> dict[str, Any]:
    try:
        value = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def initial_delivery(project: Project) -> dict[str, Any]:
    config = config_for(project)
    current = config.get("delivery")
    if isinstance(current, dict):
        state = dict(current)
        state.setdefault("providers", {})
        state.setdefault("checks", [])
        state.setdefault("requested", [])
        state.setdefault("automatic", True)
        state.setdefault("retry_count", 0)
        state.setdefault("next_retry_at", "")
        state.setdefault("admin_attention", False)
        state.setdefault("last_error", "")
        state.setdefault("url", "")
        return state
    return {
        "status": "pending",
        "url": "",
        "providers": {},
        "checks": [],
        "requested": [],
        "automatic": False,
        "retry_count": 0,
        "next_retry_at": "",
        "admin_attention": False,
        "last_error": "",
        "updated_at": _iso(utcnow()),
    }


def automatic_delivery_state() -> dict[str, Any]:
    return {
        "status": "pending",
        "url": "",
        "providers": {},
        "checks": [],
        "requested": [],
        "automatic": True,
        "retry_count": 0,
        "next_retry_at": _iso(utcnow()),
        "admin_attention": False,
        "last_error": "",
        "updated_at": _iso(utcnow()),
    }


def save_delivery(db: Session, project: Project, delivery: dict[str, Any]) -> None:
    config = config_for(project)
    config["delivery"] = delivery
    project.codex_config = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    db.commit()


def _current_credential(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{CURRENT_PROVIDER_PREFIX}{provider}",
            ProviderCredential.label == CURRENT_CREDENTIAL_LABEL,
        )
    )


def _legacy_credential(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{LEGACY_PROVIDER_PREFIX}{provider}",
            ProviderCredential.label == LEGACY_CREDENTIAL_LABEL,
        )
    )


def _metadata(item: ProviderCredential) -> dict[str, Any]:
    try:
        value = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def connection(db: Session, workspace_id: str, provider: str) -> tuple[str, str] | None:
    """Read the Super Admin cloud credential, with legacy delivery credentials as fallback."""
    current = _current_credential(db, workspace_id, provider)
    if current and current.enabled:
        try:
            token = Vault().decrypt(current.encrypted_secret).strip()
        except ValueError:
            token = ""
        if token:
            return token, str(_metadata(current).get("scope") or "").strip()

    legacy = _legacy_credential(db, workspace_id, provider)
    if not legacy or not legacy.enabled:
        return None
    try:
        payload = json.loads(Vault().decrypt(legacy.encrypted_secret))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    token = str(payload.get("token") or "").strip()
    if not token:
        return None
    return token, str(payload.get("account_id") or "").strip()


def repository_full_name(db: Session, project: Project) -> str:
    repository = db.scalar(select(Repository).where(Repository.project_id == project.id))
    if repository and repository.full_name:
        return repository.full_name
    value = str(project.repository_url or "").removesuffix(".git")
    if "github.com/" in value:
        return value.split("github.com/", 1)[1].strip("/")
    if value.startswith("git@github.com:"):
        return value.split(":", 1)[1].strip("/")
    return value.strip("/")


def selected_providers(project: Project) -> list[str]:
    config = config_for(project)
    blueprint = config.get("project_blueprint")
    if not isinstance(blueprint, dict):
        return list(PROVIDERS)
    databases = {str(x).lower() for x in blueprint.get("databases", []) if x}
    backend = {str(x).lower() for x in blueprint.get("backend", []) if x}
    frontend = {str(x).lower() for x in blueprint.get("frontend", []) if x}
    selected: list[str] = []
    if not databases or "postgresql" in databases:
        selected.append("neon")
    if not backend or any(x != "none" for x in backend):
        selected.append("render")
    if not frontend or any(x != "none" for x in frontend):
        selected.append("vercel")
    return selected


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def request_json(
    client: httpx.Client,
    provider: str,
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    try:
        response = client.request(
            method,
            url,
            headers=headers(token),
            json=payload,
            params=params,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"{provider}: indisponível") from error
    if response.status_code >= 400:
        raise RuntimeError(f"{provider}: HTTP {response.status_code}")
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(f"{provider}: resposta inválida") from error


def _vercel_scope_params(scope: str) -> dict[str, str] | None:
    if not scope:
        return None
    if scope.startswith("team_"):
        return {"teamId": scope}
    return {"slug": scope}


def provision_neon(
    client: httpx.Client,
    token: str,
    account_id: str,
    project: Project,
    state: dict[str, Any],
) -> str:
    neon = state.setdefault("providers", {}).setdefault("neon", {})
    if not neon.get("project_id"):
        body: dict[str, Any] = {
            "name": project.slug,
            "pg_version": 18,
            "branch": {"name": "main", "role_name": "app", "database_name": "app"},
        }
        if account_id:
            body["org_id"] = account_id
        created = request_json(
            client,
            "neon",
            "POST",
            f"{NEON_API}/projects",
            token,
            payload={"project": body},
        ) or {}
        project_data = created.get("project") or {}
        branch = created.get("branch") or {}
        databases = created.get("databases") or [{}]
        roles = created.get("roles") or [{}]
        neon.update(
            {
                "project_id": str(project_data.get("id") or ""),
                "main_branch_id": str(branch.get("id") or ""),
                "database_name": str(databases[0].get("name") or "app"),
                "role_name": str(roles[0].get("name") or "app"),
            }
        )
        if not neon["project_id"] or not neon["main_branch_id"]:
            raise RuntimeError("neon: IDs não retornados")

    if not neon.get("homolog_branch_id"):
        created = request_json(
            client,
            "neon",
            "POST",
            f"{NEON_API}/projects/{neon['project_id']}/branches",
            token,
            payload={
                "branch": {"name": "homolog", "parent_id": neon["main_branch_id"]},
                "endpoints": [{"type": "read_write"}],
            },
        ) or {}
        neon["homolog_branch_id"] = str((created.get("branch") or {}).get("id") or "")
        if not neon["homolog_branch_id"]:
            raise RuntimeError("neon: homologação não retornada")

    uri = request_json(
        client,
        "neon",
        "GET",
        f"{NEON_API}/projects/{neon['project_id']}/connection_uri",
        token,
        params={
            "branch_id": neon["homolog_branch_id"],
            "database_name": neon.get("database_name") or "app",
            "role_name": neon.get("role_name") or "app",
            "pooled": "true",
        },
    ) or {}
    database_url = str(uri.get("uri") or "")
    if not database_url:
        raise RuntimeError("neon: DATABASE_URL não retornada")
    neon["status"] = "ready"
    return database_url


def provision_render(
    client: httpx.Client,
    token: str,
    account_id: str,
    project: Project,
    state: dict[str, Any],
    database_url: str | None,
) -> str:
    render = state.setdefault("providers", {}).setdefault("render", {})
    if render.get("service_id") and render.get("url"):
        return str(render["url"])
    if not account_id:
        raise RuntimeError("render: owner ID não configurado")

    body: dict[str, Any] = {
        "type": "web_service",
        "name": f"{project.slug}-homolog",
        "ownerId": account_id,
        "repo": project.repository_url,
        "branch": project.default_branch or "main",
        "autoDeploy": "yes",
        "envVars": [{"key": "APP_ENV", "value": "homolog"}],
        "serviceDetails": {
            "runtime": "docker",
            "plan": "free",
            "healthCheckPath": "/health",
            "envSpecificDetails": {"dockerfilePath": "./Dockerfile"},
        },
    }
    if database_url:
        body["envVars"].append({"key": "DATABASE_URL", "value": database_url})
    created = request_json(
        client,
        "render",
        "POST",
        f"{RENDER_API}/services",
        token,
        payload=body,
    ) or {}
    service = created.get("service") if isinstance(created.get("service"), dict) else created
    render["service_id"] = str(service.get("id") or "")
    render["url"] = str((service.get("serviceDetails") or {}).get("url") or service.get("url") or "")
    if not render["service_id"]:
        raise RuntimeError("render: serviço não retornado")
    render["status"] = "provisioned"
    return str(render.get("url") or "")


def provision_vercel(
    client: httpx.Client,
    token: str,
    account_id: str,
    project: Project,
    state: dict[str, Any],
    backend_url: str | None,
    repo_full_name: str,
) -> str:
    vercel = state.setdefault("providers", {}).setdefault("vercel", {})
    params = _vercel_scope_params(account_id)
    if not vercel.get("project_id"):
        created = request_json(
            client,
            "vercel",
            "POST",
            f"{VERCEL_API}/v11/projects",
            token,
            params=params,
            payload={
                "name": project.slug,
                "gitRepository": {"type": "github", "repo": repo_full_name},
            },
        ) or {}
        vercel["project_id"] = str(created.get("id") or "")
        if not vercel["project_id"]:
            raise RuntimeError("vercel: projeto não retornado")

    if backend_url and not vercel.get("backend_configured"):
        env_params: dict[str, Any] = {"upsert": "true"}
        if params:
            env_params.update(params)
        request_json(
            client,
            "vercel",
            "POST",
            f"{VERCEL_API}/v10/projects/{vercel['project_id']}/env",
            token,
            params=env_params,
            payload=[
                {
                    "key": key,
                    "value": backend_url,
                    "type": "encrypted",
                    "target": ["production", "preview"],
                }
                for key in ("APP_BACKEND_URL", "NEXT_PUBLIC_API_URL", "VITE_API_URL")
            ],
        )
        vercel["backend_configured"] = True

    if not vercel.get("deployment_id"):
        deploy_params: dict[str, Any] = {"skipAutoDetectionConfirmation": "1"}
        if params:
            deploy_params.update(params)
        parts = repo_full_name.split("/", 1)
        if len(parts) != 2:
            raise RuntimeError("vercel: repositório GitHub inválido")
        deployed = request_json(
            client,
            "vercel",
            "POST",
            f"{VERCEL_API}/v13/deployments",
            token,
            params=deploy_params,
            payload={
                "name": project.slug,
                "project": vercel["project_id"],
                "gitSource": {
                    "type": "github",
                    "org": parts[0],
                    "repo": parts[1],
                    "ref": project.default_branch or "main",
                },
            },
        ) or {}
        vercel["deployment_id"] = str(deployed.get("id") or "")
        raw_url = str(deployed.get("url") or "").strip()
        if raw_url and not raw_url.startswith(("http://", "https://")):
            raw_url = f"https://{raw_url}"
        vercel["url"] = raw_url
        if not vercel["deployment_id"]:
            raise RuntimeError("vercel: deployment não retornado")
    vercel["status"] = "deploying"
    return str(vercel.get("url") or "")


def verify(state: dict[str, Any]) -> dict[str, Any]:
    providers = state.get("providers") if isinstance(state.get("providers"), dict) else {}
    render_url = str((providers.get("render") or {}).get("url") or "").rstrip("/")
    vercel_url = str((providers.get("vercel") or {}).get("url") or "").rstrip("/")
    targets: list[tuple[str, str]] = []
    if render_url:
        targets.append(("backend", f"{render_url}/health"))
    if vercel_url:
        targets.append(("frontend", vercel_url))
        targets.append(("database", f"{vercel_url}/health"))

    checks: list[dict[str, Any]] = []
    with httpx.Client(timeout=12.0, follow_redirects=True) as client:
        for name, url in targets:
            try:
                response = client.get(url, headers={"Accept": "application/json,text/html"})
                status_code = response.status_code
                ok = 200 <= status_code < 300
            except httpx.HTTPError:
                status_code = 0
                ok = False
            checks.append({"name": name, "ok": ok, "status_code": status_code, "url": url})

    required = {"backend", "frontend", "database"}
    seen = {check["name"] for check in checks if check["ok"]}
    ready = required.issubset(seen)
    return {
        "status": "ready" if ready else "deploying",
        "url": vercel_url or render_url,
        "checks": checks,
        "verified_at": _iso(utcnow()),
    }


def _retry_delay(retry_count: int) -> int:
    index = max(0, min(retry_count - 1, len(RETRY_DELAYS_SECONDS) - 1))
    return RETRY_DELAYS_SECONDS[index]


def run_delivery(db: Session, project: Project, actor: str) -> dict[str, Any]:
    if not project.repository_url:
        raise RuntimeError("delivery: projeto sem repositório")

    state = initial_delivery(project)
    state["automatic"] = bool(state.get("automatic", True))
    state["status"] = "provisioning"
    state["last_error"] = ""
    state["updated_at"] = _iso(utcnow())
    state["admin_attention"] = False
    selected = selected_providers(project)
    state["requested"] = selected

    missing = [name for name in selected if connection(db, project.workspace_id, name) is None]
    if missing:
        state["status"] = "blocked"
        state["blocked_providers"] = missing
        state["last_error"] = "Infraestrutura ainda não configurada pela administração."
        state["next_retry_at"] = ""
        state["admin_attention"] = True
        state["updated_at"] = _iso(utcnow())
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor=actor,
            action="project.delivery_blocked",
            outcome="blocked",
            details={"missing_providers": missing},
        )
        save_delivery(db, project, state)
        return state

    state.pop("blocked_providers", None)
    database_url: str | None = None
    backend_url: str | None = None
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            if "neon" in selected:
                token, account_id = connection(db, project.workspace_id, "neon") or ("", "")
                database_url = provision_neon(client, token, account_id, project, state)
                save_delivery(db, project, state)
            if "render" in selected:
                token, account_id = connection(db, project.workspace_id, "render") or ("", "")
                backend_url = provision_render(client, token, account_id, project, state, database_url)
                save_delivery(db, project, state)
            if "vercel" in selected:
                token, account_id = connection(db, project.workspace_id, "vercel") or ("", "")
                provision_vercel(
                    client,
                    token,
                    account_id,
                    project,
                    state,
                    backend_url,
                    repository_full_name(db, project),
                )
                save_delivery(db, project, state)
    except RuntimeError as error:
        provider = str(error).split(":", 1)[0].strip().lower()
        retry_count = int(state.get("retry_count") or 0) + 1
        state["status"] = "failed"
        state["failed_provider"] = provider if provider in PROVIDERS else "cloud"
        state["last_error"] = "Não foi possível concluir esta etapa automaticamente."
        state["retry_count"] = retry_count
        state["updated_at"] = _iso(utcnow())
        if state["automatic"] and retry_count < MAX_AUTO_RETRIES:
            state["next_retry_at"] = _iso(utcnow() + timedelta(seconds=_retry_delay(retry_count)))
            state["admin_attention"] = False
        else:
            state["next_retry_at"] = ""
            state["admin_attention"] = True
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor=actor,
            action="project.delivery_failed",
            outcome="failed",
            details={
                "provider": state["failed_provider"],
                "error": str(error)[:300],
                "retry_count": retry_count,
                "auto_retry": bool(state.get("next_retry_at")),
            },
        )
        save_delivery(db, project, state)
        return state

    result = verify(state)
    state.update(result)
    state["updated_at"] = _iso(utcnow())
    state["failed_provider"] = ""
    state["last_error"] = ""
    state["admin_attention"] = False
    if state["status"] == "ready":
        state["retry_count"] = 0
        state["next_retry_at"] = ""
        vercel = state.get("providers", {}).get("vercel") or {}
        if isinstance(vercel, dict):
            vercel["status"] = "ready"
    else:
        state["next_retry_at"] = _iso(utcnow() + timedelta(seconds=60))

    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=actor,
        action="project.delivery_verified",
        outcome="success" if state["status"] == "ready" else "pending",
        details={
            "status": state["status"],
            "checks": [
                {"name": item["name"], "ok": item["ok"], "status_code": item["status_code"]}
                for item in state.get("checks", [])
            ],
        },
    )
    save_delivery(db, project, state)
    return state


def public_delivery_state(state: dict[str, Any], *, super_admin: bool) -> dict[str, Any]:
    """Hide provider diagnostics from regular users while preserving the ready product URL."""
    if super_admin:
        return state
    status = str(state.get("status") or "pending")
    if status == "ready":
        return {
            "status": "ready",
            "url": str(state.get("url") or ""),
            "checks": [
                {"name": str(item.get("name") or ""), "ok": bool(item.get("ok"))}
                for item in state.get("checks", [])
                if isinstance(item, dict)
            ],
            "last_error": "",
            "updated_at": state.get("updated_at", ""),
        }
    return {
        "status": "deploying",
        "url": "",
        "checks": [],
        "last_error": "",
        "updated_at": state.get("updated_at", ""),
    }


def _missing_connections(db: Session, project: Project, state: dict[str, Any]) -> list[str]:
    requested = state.get("requested")
    selected = [str(item) for item in requested] if isinstance(requested, list) and requested else selected_providers(project)
    return [name for name in selected if connection(db, project.workspace_id, name) is None]


def delivery_due(db: Session, project: Project, now: datetime | None = None) -> bool:
    config = config_for(project)
    raw = config.get("delivery")
    if not isinstance(raw, dict):
        return False
    state = initial_delivery(project)
    if not state.get("automatic", True) or not project.repository_url:
        return False
    status = str(state.get("status") or "pending")
    if status == "ready":
        return False
    if status == "blocked":
        return not _missing_connections(db, project, state)
    if status == "failed" and bool(state.get("admin_attention")):
        return False
    due = _parse_iso(str(state.get("next_retry_at") or ""))
    return due is None or due <= (now or utcnow())


def delivery_alerts(db: Session, workspace_id: str) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    projects = db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all()
    for project in projects:
        state = initial_delivery(project)
        if not isinstance(config_for(project).get("delivery"), dict):
            continue
        status = str(state.get("status") or "pending")
        if not bool(state.get("admin_attention")) and status not in {"blocked"}:
            continue
        alerts.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "status": status,
                "blocked_providers": [str(item) for item in state.get("blocked_providers", [])],
                "failed_provider": str(state.get("failed_provider") or ""),
                "retry_count": int(state.get("retry_count") or 0),
                "last_error": str(state.get("last_error") or ""),
                "updated_at": str(state.get("updated_at") or ""),
            }
        )
    return alerts
