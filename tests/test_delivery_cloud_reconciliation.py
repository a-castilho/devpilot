from types import SimpleNamespace

import pytest

from app import delivery_cloud_bridge as bridge


def test_vercel_scope_candidates_support_single_team():
    assert bridge._scope_candidates(
        "vercel",
        {"teams": [{"id": "team_example", "slug": "example"}]},
    ) == ["team_example"]


def test_neon_locked_request_retries(monkeypatch):
    calls = {"count": 0}

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("neon: HTTP 423")
        return {"ok": True}

    monkeypatch.setattr(bridge, "_ORIGINAL_REQUEST_JSON", fake_request)
    monkeypatch.setattr(bridge.time, "sleep", lambda _: None)

    result = bridge._request_json_with_cloud_scope(
        object(),
        "neon",
        "POST",
        "https://console.neon.tech/api/v2/projects/prj/branches",
        "token-123456",
        payload={"branch": {"name": "homolog"}},
    )

    assert result == {"ok": True}
    assert calls["count"] == 3


def test_neon_existing_project_is_reused_and_hydrated(monkeypatch):
    calls = []

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        calls.append(url)
        if url.endswith("/projects"):
            return {
                "projects": [
                    {
                        "id": "project-new",
                        "name": "regulaai",
                        "created_at": "2026-08-31T00:38:10Z",
                    },
                    {
                        "id": "project-old",
                        "name": "regulaai",
                        "created_at": "2026-08-16T18:59:33Z",
                    },
                ]
            }
        if url.endswith("/projects/project-new/branches"):
            return {
                "branches": [
                    {"id": "br-main", "name": "main", "default": True},
                    {"id": "br-homolog", "name": "homolog"},
                ]
            }
        if url.endswith("/databases"):
            return {"databases": [{"name": "app"}]}
        if url.endswith("/roles"):
            return {"roles": [{"name": "app", "protected": False}]}
        raise AssertionError(url)

    captured = {}

    def fake_provision(client, token, account_id, project, state):
        captured.update(state["providers"]["neon"])
        return "postgresql://example"

    monkeypatch.setattr(bridge, "_ORIGINAL_REQUEST_JSON", fake_request)
    monkeypatch.setattr(bridge, "_ORIGINAL_PROVISION_NEON", fake_provision)

    state = {"providers": {}}
    result = bridge._provision_neon_reconciled(
        object(),
        "neon-token",
        "org-example",
        SimpleNamespace(slug="regulaai"),
        state,
    )

    assert result == "postgresql://example"
    assert captured["project_id"] == "project-new"
    assert captured["main_branch_id"] == "br-main"
    assert captured["homolog_branch_id"] == "br-homolog"
    assert captured["database_name"] == "app"
    assert captured["role_name"] == "app"
    assert captured["reused"] is True


def test_render_existing_service_is_reused(monkeypatch):
    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        return [
            {
                "service": {
                    "id": "srv-example",
                    "name": "regulaai-homolog",
                    "createdAt": "2026-08-31T00:00:00Z",
                    "serviceDetails": {"url": "https://regulaai-homolog.onrender.com"},
                }
            }
        ]

    captured = {}

    def fake_provision(client, token, account_id, project, state, database_url):
        captured.update(state["providers"]["render"])
        return captured.get("url", "")

    monkeypatch.setattr(bridge, "_ORIGINAL_REQUEST_JSON", fake_request)
    monkeypatch.setattr(bridge, "_ORIGINAL_PROVISION_RENDER", fake_provision)

    state = {"providers": {}}
    result = bridge._provision_render_reconciled(
        object(),
        "render-token",
        "tea-example",
        SimpleNamespace(slug="regulaai"),
        state,
        "postgresql://example",
    )

    assert result == "https://regulaai-homolog.onrender.com"
    assert captured["service_id"] == "srv-example"
    assert captured["reused"] is True


def test_vercel_existing_project_is_reused(monkeypatch):
    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        assert provider == "vercel"
        assert method == "GET"
        assert url.endswith("/v9/projects/regulaai")
        assert params == {"teamId": "team_example"}
        return {"id": "prj_example", "name": "regulaai"}

    captured = {}

    def fake_provision(client, token, account_id, project, state, backend_url, repo_full_name):
        captured.update(state["providers"]["vercel"])
        return "https://regulaai.vercel.app"

    monkeypatch.setattr(bridge, "_ORIGINAL_REQUEST_JSON", fake_request)
    monkeypatch.setattr(bridge, "_ORIGINAL_PROVISION_VERCEL", fake_provision)

    state = {"providers": {}}
    result = bridge._provision_vercel_reconciled(
        object(),
        "vercel-token",
        "team_example",
        SimpleNamespace(slug="regulaai"),
        state,
        "https://backend.onrender.com",
        "acastilho/regulaai",
    )

    assert result == "https://regulaai.vercel.app"
    assert captured["project_id"] == "prj_example"
    assert captured["reused"] is True


def test_optional_request_only_swallows_404(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_ORIGINAL_REQUEST_JSON",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vercel: HTTP 404")),
    )
    assert bridge._optional_request_json(
        object(),
        "vercel",
        "GET",
        "https://api.vercel.com/v9/projects/missing",
        "token",
    ) is None

    monkeypatch.setattr(
        bridge,
        "_ORIGINAL_REQUEST_JSON",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vercel: HTTP 401")),
    )
    with pytest.raises(RuntimeError, match="HTTP 401"):
        bridge._optional_request_json(
            object(),
            "vercel",
            "GET",
            "https://api.vercel.com/v9/projects/missing",
            "token",
        )
