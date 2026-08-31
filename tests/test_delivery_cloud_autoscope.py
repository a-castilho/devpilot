from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.delivery_cloud_bridge import (
    _discover_scope,
    _request_json_with_cloud_scope,
    _scope_candidates,
    cloud_admin_connection,
)
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_scope_candidates_support_neon_and_render_wrappers():
    assert _scope_candidates(
        "neon",
        {"organizations": [{"id": "org-example"}]},
    ) == ["org-example"]
    assert _scope_candidates(
        "render",
        [{"owner": {"id": "tea-example"}}],
    ) == ["tea-example"]


def test_neon_scope_is_discovered_from_api_key(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"organizations": [{"id": "org-example"}]})

    monkeypatch.setattr("app.delivery_cloud_bridge.httpx.get", fake_get)

    assert _discover_scope("neon", "neon-token-123456") == "org-example"
    assert calls[0][0] == "https://console.neon.tech/api/v2/users/me/organizations"


def test_render_scope_is_discovered_from_api_key(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse([{"owner": {"id": "tea-example"}}])

    monkeypatch.setattr("app.delivery_cloud_bridge.httpx.get", fake_get)

    assert _discover_scope("render", "render-token-123456") == "tea-example"
    assert calls[0][0] == "https://api.render.com/v1/owners"


def test_existing_cloud_admin_key_uses_discovered_scope(monkeypatch):
    monkeypatch.setattr(
        "app.delivery_cloud_bridge._discover_scope",
        lambda provider, token: "org-example" if provider == "neon" else "",
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            workspace = Workspace(name="DevPilot", slug="default")
            db.add(workspace)
            db.flush()
            db.add(
                ProviderCredential(
                    workspace_id=workspace.id,
                    provider="cloud:neon",
                    label="cloud-admin",
                    encrypted_secret=Vault().encrypt("neon-token-123456"),
                    models='{"scope":""}',
                    enabled=True,
                )
            )
            db.commit()

            assert cloud_admin_connection(db, workspace.id, "neon") == (
                "neon-token-123456",
                "org-example",
            )
    finally:
        engine.dispose()


def test_neon_org_id_is_moved_from_project_body_to_query_params(monkeypatch):
    captured = {}

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        captured["payload"] = payload
        captured["params"] = params
        return {"project": {"id": "project-example"}}

    monkeypatch.setattr("app.delivery_cloud_bridge._ORIGINAL_REQUEST_JSON", fake_request)

    result = _request_json_with_cloud_scope(
        object(),
        "neon",
        "POST",
        "https://console.neon.tech/api/v2/projects",
        "neon-token-123456",
        payload={
            "project": {
                "name": "example",
                "pg_version": 18,
                "org_id": "org-example",
            }
        },
    )

    assert result == {"project": {"id": "project-example"}}
    assert captured["params"] == {"org_id": "org-example"}
    assert captured["payload"]["project"] == {
        "name": "example",
        "pg_version": 18,
    }
