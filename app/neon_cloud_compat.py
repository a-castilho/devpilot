from __future__ import annotations

from typing import Any

from app import cloud_admin_routes

_NEON_API = "https://console.neon.tech/api/v2"
_ORIGINAL_PROVIDER_REQUEST = cloud_admin_routes._provider_request


def _response_detail(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:320]
        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "code"):
                value = error.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:320]
    text = str(getattr(response, "text", "") or "").strip()
    return text[:320]


def _neon_get(secret: str, path: str, params: dict[str, Any] | None = None):
    return cloud_admin_routes._retry_request(
        "GET",
        f"{_NEON_API}{path}",
        headers=cloud_admin_routes._headers("neon", secret),
        params=params,
    )


def _organization_ids(secret: str) -> list[str]:
    response = _neon_get(secret, "/users/me/organizations")
    if response.status_code in {401, 403}:
        detail = _response_detail(response)
        suffix = f": {detail}" if detail else ""
        raise cloud_admin_routes.CloudProviderError(
            f"Neon recusou a API key (HTTP {response.status_code}){suffix}."
        )
    if response.status_code >= 400:
        return []
    try:
        data = response.json()
    except ValueError:
        return []

    if isinstance(data, dict):
        source = data.get("organizations")
        if not isinstance(source, list):
            source = data.get("orgs")
    else:
        source = data
    if not isinstance(source, list):
        return []

    result: list[str] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        org_id = str(item.get("id") or item.get("org_id") or "").strip()
        if org_id and org_id not in result:
            result.append(org_id)
    return result


def _load_projects(secret: str, scope: str) -> dict[str, Any]:
    organizations = _organization_ids(secret)
    candidates: list[str] = []

    def add(candidate: str) -> None:
        candidate = candidate.strip()
        if candidate not in candidates:
            candidates.append(candidate)

    if scope:
        add(scope)
    add("")
    for org_id in organizations:
        add(org_id)

    projects_by_id: dict[str, dict[str, Any]] = {}
    successful_scopes: list[str] = []
    failures: list[str] = []

    for candidate in candidates:
        params: dict[str, Any] = {"limit": 50}
        if candidate:
            params["org_id"] = candidate
        response = _neon_get(secret, "/projects", params=params)
        if response.status_code >= 400:
            detail = _response_detail(response)
            label = candidate or "escopo automático"
            failures.append(
                f"{label}: HTTP {response.status_code}" + (f" — {detail}" if detail else "")
            )
            continue
        try:
            payload = response.json()
        except ValueError:
            failures.append(f"{candidate or 'escopo automático'}: resposta JSON inválida")
            continue

        source = payload.get("projects") if isinstance(payload, dict) else None
        if not isinstance(source, list):
            failures.append(f"{candidate or 'escopo automático'}: resposta sem lista de projetos")
            continue

        successful_scopes.append(candidate)
        for project in source:
            if not isinstance(project, dict):
                continue
            project_id = str(project.get("id") or "").strip()
            key = project_id or str(project.get("name") or len(projects_by_id))
            projects_by_id[key] = project

    if not successful_scopes:
        detail = "; ".join(failures[:3])
        if not detail:
            detail = "A API não retornou um escopo utilizável."
        raise cloud_admin_routes.CloudProviderError(
            "Neon não conseguiu validar a credencial. " + detail
        )

    return {
        "projects": list(projects_by_id.values())[:50],
        "_devpilot_neon": {
            "organizations": organizations,
            "resolved_scope": successful_scopes[0],
            "successful_scopes": successful_scopes,
            "diagnostics": failures[:3],
        },
    }


def _provider_request(provider: str, secret: str, scope: str, *, resources: bool) -> Any:
    if provider != "neon":
        return _ORIGINAL_PROVIDER_REQUEST(provider, secret, scope, resources=resources)
    return _load_projects(secret, scope.strip())


cloud_admin_routes._provider_request = _provider_request
