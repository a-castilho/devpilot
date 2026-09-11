from __future__ import annotations

from urllib.parse import quote

import httpx

from app import product_delivery_routes as delivery

_ORIGINAL_RENDER = delivery.provision_render
_ORIGINAL_VERCEL = delivery.provision_vercel


def _render_existing(client: httpx.Client, token: str, account_id: str, project, state) -> bool:
    try:
        response = client.get(
            f"{delivery.RENDER_API}/services",
            headers=delivery.headers(token),
            params={"ownerId": account_id, "limit": 100},
        )
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    expected_name = f"{project.slug}-homolog"
    expected_repo = str(project.repository_url or "").removesuffix(".git").rstrip("/")
    for wrapper in payload if isinstance(payload, list) else []:
        if not isinstance(wrapper, dict):
            continue
        service = wrapper.get("service") if isinstance(wrapper.get("service"), dict) else wrapper
        if not isinstance(service, dict) or str(service.get("name") or "") != expected_name:
            continue
        repo = str(service.get("repo") or "").removesuffix(".git").rstrip("/")
        if repo and expected_repo and repo != expected_repo:
            continue
        details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), dict) else {}
        render = state.setdefault("providers", {}).setdefault("render", {})
        render["service_id"] = str(service.get("id") or "")
        render["url"] = str(details.get("url") or service.get("url") or "")
        render["status"] = "provisioned"
        return bool(render["service_id"])
    return False


def provision_render_idempotent(client, token, account_id, project, state, database_url):
    render = state.setdefault("providers", {}).setdefault("render", {})
    if not (render.get("service_id") and render.get("url")):
        _render_existing(client, token, account_id, project, state)
    return _ORIGINAL_RENDER(client, token, account_id, project, state, database_url)


def _vercel_existing_project(client: httpx.Client, token: str, account_id: str, project, state) -> bool:
    params = {"teamId": account_id} if account_id else None
    try:
        response = client.get(
            f"{delivery.VERCEL_API}/v9/projects/{quote(project.slug, safe='')}",
            headers=delivery.headers(token),
            params=params,
        )
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        data = response.json()
    except ValueError:
        return False
    vercel = state.setdefault("providers", {}).setdefault("vercel", {})
    vercel["project_id"] = str(data.get("id") or "")
    return bool(vercel["project_id"])


def _vercel_existing_deployment(client: httpx.Client, token: str, account_id: str, state) -> bool:
    vercel = state.setdefault("providers", {}).setdefault("vercel", {})
    project_id = str(vercel.get("project_id") or "").strip()
    if not project_id:
        return False
    params = {"projectId": project_id, "limit": 5}
    if account_id:
        params["teamId"] = account_id
    try:
        response = client.get(
            f"{delivery.VERCEL_API}/v6/deployments",
            headers=delivery.headers(token),
            params=params,
        )
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        data = response.json()
    except ValueError:
        return False
    deployments = data.get("deployments") if isinstance(data, dict) else []
    if not isinstance(deployments, list):
        return False
    for item in deployments:
        if not isinstance(item, dict):
            continue
        state_name = str(item.get("state") or item.get("readyState") or "").upper()
        if state_name not in {"READY", "BUILDING", "QUEUED", "INITIALIZING"}:
            continue
        deployment_id = str(item.get("uid") or item.get("id") or "")
        url = str(item.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        if deployment_id:
            vercel["deployment_id"] = deployment_id
            vercel["url"] = url
            vercel["status"] = "ready" if state_name == "READY" else "deploying"
            return True
    return False


def provision_vercel_idempotent(client, token, account_id, project, state, backend_url, repo_full_name):
    vercel = state.setdefault("providers", {}).setdefault("vercel", {})
    if not vercel.get("project_id"):
        _vercel_existing_project(client, token, account_id, project, state)
    if vercel.get("project_id") and not vercel.get("deployment_id"):
        _vercel_existing_deployment(client, token, account_id, state)
    try:
        return _ORIGINAL_VERCEL(client, token, account_id, project, state, backend_url, repo_full_name)
    except RuntimeError as error:
        if "HTTP 409" not in str(error):
            raise
        # A 409 means the intended idempotent object already exists or a deployment
        # is already in flight. Discover it and continue instead of creating copies.
        _vercel_existing_project(client, token, account_id, project, state)
        if _vercel_existing_deployment(client, token, account_id, state):
            return str((state.get("providers", {}).get("vercel") or {}).get("url") or "")
        raise


def install() -> None:
    delivery.provision_render = provision_render_idempotent
    delivery.provision_vercel = provision_vercel_idempotent


install()
