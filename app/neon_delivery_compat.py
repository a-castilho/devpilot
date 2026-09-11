from __future__ import annotations

from typing import Any

import httpx

from app import product_delivery_routes as delivery
from app.neon_delivery_scope import resolve_org_id, response_detail

_ORIGINAL_PROVISION_NEON = delivery.provision_neon
_ORIGINAL_REQUEST_JSON = delivery.request_json


def _request_json(
    client: httpx.Client,
    provider: str,
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    if provider != "neon":
        return _ORIGINAL_REQUEST_JSON(
            client, provider, method, url, token, payload=payload, params=params
        )
    try:
        response = client.request(
            method,
            url,
            headers=delivery.headers(token),
            json=payload,
            params=params,
        )
    except httpx.HTTPError as error:
        raise RuntimeError("neon: indisponível") from error
    if response.status_code >= 400:
        detail = response_detail(response)
        raise RuntimeError(
            f"neon: HTTP {response.status_code}" + (f" — {detail}" if detail else "")
        )
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError("neon: resposta inválida") from error


def _provision_neon(client, token, account_id, project, state):
    resolved_org_id = resolve_org_id(client, token, account_id)
    neon = state.setdefault("providers", {}).setdefault("neon", {})
    if resolved_org_id:
        neon["organization_id"] = resolved_org_id
    return _ORIGINAL_PROVISION_NEON(
        client, token, resolved_org_id, project, state
    )


def install() -> None:
    delivery.request_json = _request_json
    delivery.provision_neon = _provision_neon


install()
