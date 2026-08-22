from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.cloud_provisioning import CloudConnection, VERCEL_API


class HomologationError(RuntimeError):
    pass


def _request_vercel(
    connection: CloudConnection,
    *,
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
) -> Any:
    request_params = dict(params or {})
    if connection.account_id:
        request_params["teamId"] = connection.account_id
    headers = {
        "Authorization": f"Bearer {connection.token}",
        "Accept": "application/json",
    }
    if json is not None:
        headers["Content-Type"] = "application/json"

    owns_client = client is None
    worker = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        response = worker.request(
            method,
            f"{VERCEL_API}{path}",
            headers=headers,
            params=request_params or None,
            json=json,
        )
    except httpx.HTTPError as error:
        raise HomologationError("Vercel indisponível para iniciar homologação.") from error
    finally:
        if owns_client:
            worker.close()

    if response.status_code >= 400:
        raise HomologationError(
            f"Vercel não iniciou a homologação (HTTP {response.status_code})."
        )
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise HomologationError("Vercel retornou resposta inválida ao iniciar homologação.") from error


def trigger_vercel_homologation(
    *,
    connection: CloudConnection,
    project_id: str,
    project_name: str,
    repository_full_name: str,
    branch: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Create a preview deployment from the project's GitHub main branch."""
    parts = [part for part in repository_full_name.strip("/").split("/") if part]
    if len(parts) != 2:
        raise HomologationError("Repositório GitHub inválido para a homologação Vercel.")
    organization, repository = parts

    payload = _request_vercel(
        connection,
        method="POST",
        path="/v13/deployments",
        params={"skipAutoDetectionConfirmation": "1"},
        json={
            "name": project_name,
            "project": project_id,
            "gitSource": {
                "type": "github",
                "org": organization,
                "repo": repository,
                "ref": branch,
            },
        },
        client=client,
    )
    if not isinstance(payload, dict):
        raise HomologationError("Vercel não retornou o deployment de homologação.")

    deployment_id = str(payload.get("id") or "")
    raw_url = str(payload.get("url") or "").strip()
    if raw_url and not raw_url.startswith(("http://", "https://")):
        raw_url = f"https://{raw_url}"
    if not deployment_id:
        raise HomologationError("Vercel não retornou o ID do deployment de homologação.")

    return {
        "status": "deploying",
        "environment": "preview",
        "deployment_id": deployment_id,
        "url": raw_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _check(
    client: httpx.Client,
    *,
    name: str,
    url: str,
) -> dict[str, Any]:
    try:
        response = client.get(url, headers={"Accept": "application/json,text/html"})
        status_code = response.status_code
        ok = 200 <= status_code < 300
    except httpx.HTTPError:
        status_code = 0
        ok = False
    return {
        "name": name,
        "url": url,
        "ok": ok,
        "status_code": status_code,
    }


def verify_homologation(
    cloud_state: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Verify the public homologation path without persisting response bodies or secrets."""
    providers = cloud_state.get("providers")
    if not isinstance(providers, dict):
        providers = {}

    render = providers.get("render")
    render = render if isinstance(render, dict) else {}
    vercel = providers.get("vercel")
    vercel = vercel if isinstance(vercel, dict) else {}
    preview = vercel.get("homologation")
    preview = preview if isinstance(preview, dict) else {}

    render_url = str(render.get("url") or "").rstrip("/")
    vercel_url = str(preview.get("url") or vercel.get("url") or "").rstrip("/")

    checks: list[dict[str, Any]] = []
    owns_client = client is None
    worker = client or httpx.Client(timeout=12.0, follow_redirects=True)
    try:
        if render_url:
            checks.append(
                _check(worker, name="render_health", url=f"{render_url}/health")
            )
        if vercel_url:
            checks.append(_check(worker, name="vercel_frontend", url=vercel_url))
            if render_url:
                checks.append(
                    _check(worker, name="vercel_backend_proxy", url=f"{vercel_url}/health")
                )
    finally:
        if owns_client:
            worker.close()

    ready = bool(checks) and all(check["ok"] for check in checks)
    return {
        "status": "ready" if ready else "pending",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "url": vercel_url or render_url,
        "checks": checks,
    }
