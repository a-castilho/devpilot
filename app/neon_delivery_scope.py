from __future__ import annotations

from typing import Any

import httpx

_NEON_API = "https://console.neon.tech/api/v2"


def _detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:320]
        nested = payload.get("error")
        if isinstance(nested, dict):
            for key in ("message", "detail", "code"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:320]
    return str(response.text or "").strip()[:320]


def organization_ids(client: httpx.Client, token: str) -> list[str]:
    response = client.get(
        f"{_NEON_API}/users/me/organizations",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if response.status_code in {401, 403}:
        detail = _detail(response)
        raise RuntimeError(
            f"neon: API key recusada (HTTP {response.status_code})"
            + (f" — {detail}" if detail else "")
        )
    if response.status_code >= 400:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    if isinstance(payload, dict):
        items = payload.get("organizations") or payload.get("orgs") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    result: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get("id") or item.get("org_id") or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def resolve_org_id(client: httpx.Client, token: str, configured_org_id: str = "") -> str:
    configured = str(configured_org_id or "").strip()
    if configured:
        return configured
    organizations = organization_ids(client, token)
    if len(organizations) == 1:
        return organizations[0]
    if not organizations:
        return ""
    raise RuntimeError(
        "neon: a API key possui acesso a várias organizações; configure o Organization ID explicitamente"
    )


def response_detail(response: httpx.Response) -> str:
    return _detail(response)
