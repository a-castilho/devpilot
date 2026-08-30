from __future__ import annotations

import httpx
import pytest

from app.services import provider_models
from app.services.provider_models import ProviderModelDiscoveryError, discover_provider_models


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_openai_401_is_reported_as_authentication_failure_without_provider_body(monkeypatch):
    monkeypatch.setattr(
        provider_models.httpx,
        "get",
        lambda *args, **kwargs: response(
            401,
            {"error": {"message": "sensitive account detail"}},
        ),
    )

    with pytest.raises(ProviderModelDiscoveryError, match="não autenticada") as caught:
        discover_provider_models("openai", "sk-invalid")

    assert caught.value.code == "authentication_failed"
    assert caught.value.upstream_status == 401
    assert "sensitive account detail" not in str(caught.value)


def test_openai_403_is_reported_as_catalog_permission_failure_without_provider_body(monkeypatch):
    monkeypatch.setattr(
        provider_models.httpx,
        "get",
        lambda *args, **kwargs: response(
            403,
            {"error": {"message": "sensitive permission detail"}},
        ),
    )

    with pytest.raises(ProviderModelDiscoveryError, match="negou acesso ao catálogo") as caught:
        discover_provider_models("openai", "sk-restricted")

    assert caught.value.code == "catalog_forbidden"
    assert caught.value.upstream_status == 403
    assert "permissões da API key" in str(caught.value)
    assert "sensitive permission detail" not in str(caught.value)


def test_rate_limit_keeps_distinct_machine_readable_classification(monkeypatch):
    monkeypatch.setattr(
        provider_models.httpx,
        "get",
        lambda *args, **kwargs: response(429, {"error": {"message": "slow down"}}),
    )

    with pytest.raises(ProviderModelDiscoveryError) as caught:
        discover_provider_models("openai", "sk-rate-limited")

    assert caught.value.code == "rate_limited"
    assert caught.value.upstream_status == 429
    assert "slow down" not in str(caught.value)
