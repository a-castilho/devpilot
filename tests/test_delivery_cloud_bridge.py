from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.delivery_cloud_bridge import (
    _connection_with_cloud_admin,
    _normalize_render_repository,
    _request_json_with_cloud_scope,
    cloud_admin_connection,
)
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault


def test_delivery_reuses_cloud_admin_credentials():
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
                    provider="cloud:vercel",
                    label="cloud-admin",
                    encrypted_secret=Vault().encrypt("vercel-secret-token-123456"),
                    models='{"scope":"team_example"}',
                    enabled=True,
                )
            )
            db.commit()

            assert cloud_admin_connection(db, workspace.id, "vercel") == (
                "vercel-secret-token-123456",
                "team_example",
            )
    finally:
        engine.dispose()


def test_disabled_cloud_admin_credential_is_not_used():
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
                    provider="cloud:render",
                    label="cloud-admin",
                    encrypted_secret=Vault().encrypt("render-secret-token-123456"),
                    models='{"scope":"owner_example"}',
                    enabled=False,
                )
            )
            db.commit()

            assert cloud_admin_connection(db, workspace.id, "render") is None
    finally:
        engine.dispose()


def test_unconfigured_trial_workspace_uses_devpilot_managed_credentials(monkeypatch):
    monkeypatch.setattr(
        "app.delivery_cloud_bridge.get_settings",
        lambda: SimpleNamespace(
            managed_trial_clouds_enabled=True,
            managed_trial_workspace_slug="default",
            managed_trial_providers={"neon", "render", "vercel"},
        ),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            platform = Workspace(name="DevPilot", slug="default")
            trial = Workspace(name="Cliente Teste", slug="cliente-teste")
            db.add_all([platform, trial])
            db.flush()
            db.add(
                ProviderCredential(
                    workspace_id=platform.id,
                    provider="cloud:vercel",
                    label="cloud-admin",
                    encrypted_secret=Vault().encrypt("devpilot-vercel-secret-123456"),
                    models='{"scope":"team_devpilot"}',
                    enabled=True,
                )
            )
            db.commit()

            assert _connection_with_cloud_admin(db, trial.id, "vercel") == (
                "devpilot-vercel-secret-123456",
                "team_devpilot",
            )
    finally:
        engine.dispose()


def test_explicit_trial_cloud_configuration_never_falls_back_to_platform(monkeypatch):
    monkeypatch.setattr(
        "app.delivery_cloud_bridge.get_settings",
        lambda: SimpleNamespace(
            managed_trial_clouds_enabled=True,
            managed_trial_workspace_slug="default",
            managed_trial_providers={"neon", "render", "vercel"},
        ),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            platform = Workspace(name="DevPilot", slug="default")
            customer = Workspace(name="Cliente", slug="cliente")
            db.add_all([platform, customer])
            db.flush()
            db.add_all(
                [
                    ProviderCredential(
                        workspace_id=platform.id,
                        provider="cloud:render",
                        label="cloud-admin",
                        encrypted_secret=Vault().encrypt("devpilot-render-secret-123456"),
                        models='{"scope":"owner_devpilot"}',
                        enabled=True,
                    ),
                    ProviderCredential(
                        workspace_id=customer.id,
                        provider="cloud:render",
                        label="cloud-admin",
                        encrypted_secret=Vault().encrypt("customer-render-secret-123456"),
                        models='{"scope":"owner_customer"}',
                        enabled=False,
                    ),
                ]
            )
            db.commit()

            assert _connection_with_cloud_admin(db, customer.id, "render") is None
    finally:
        engine.dispose()


def test_managed_trial_fallback_can_be_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.delivery_cloud_bridge.get_settings",
        lambda: SimpleNamespace(
            managed_trial_clouds_enabled=False,
            managed_trial_workspace_slug="default",
            managed_trial_providers={"neon", "render", "vercel"},
        ),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            platform = Workspace(name="DevPilot", slug="default")
            trial = Workspace(name="Cliente Teste", slug="cliente-teste")
            db.add_all([platform, trial])
            db.flush()
            db.add(
                ProviderCredential(
                    workspace_id=platform.id,
                    provider="cloud:neon",
                    label="cloud-admin",
                    encrypted_secret=Vault().encrypt("devpilot-neon-secret-123456"),
                    models='{"scope":"org_devpilot"}',
                    enabled=True,
                )
            )
            db.commit()

            assert _connection_with_cloud_admin(db, trial.id, "neon") is None
    finally:
        engine.dispose()


def test_vercel_slug_scope_is_forwarded_as_slug(monkeypatch):
    captured = {}

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        captured["params"] = params
        return {"ok": True}

    monkeypatch.setattr("app.delivery_cloud_bridge._ORIGINAL_REQUEST_JSON", fake_request)

    result = _request_json_with_cloud_scope(
        object(),
        "vercel",
        "GET",
        "https://api.vercel.com/v9/projects",
        "token-123456",
        params={"teamId": "maquina-de-leads1", "limit": 1},
    )

    assert result == {"ok": True}
    assert captured["params"]["slug"] == "maquina-de-leads1"
    assert "teamId" not in captured["params"]
    assert captured["params"]["limit"] == 1


def test_vercel_team_id_scope_stays_team_id(monkeypatch):
    captured = {}

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        captured["params"] = params
        return {"ok": True}

    monkeypatch.setattr("app.delivery_cloud_bridge._ORIGINAL_REQUEST_JSON", fake_request)

    _request_json_with_cloud_scope(
        object(),
        "vercel",
        "GET",
        "https://api.vercel.com/v9/projects",
        "token-123456",
        params={"teamId": "team_example"},
    )

    assert captured["params"] == {"teamId": "team_example"}


def test_render_repository_removes_dot_git_suffix():
    assert _normalize_render_repository(
        "https://github.com/a-castilho/site-pessoal.git"
    ) == "https://github.com/a-castilho/site-pessoal"


def test_render_repository_converts_github_ssh_to_https():
    assert _normalize_render_repository(
        "git@github.com:a-castilho/site-pessoal.git"
    ) == "https://github.com/a-castilho/site-pessoal"


def test_render_service_request_receives_canonical_repository(monkeypatch):
    captured = {}

    def fake_request(client, provider, method, url, token, *, payload=None, params=None):
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr("app.delivery_cloud_bridge._ORIGINAL_REQUEST_JSON", fake_request)

    result = _request_json_with_cloud_scope(
        object(),
        "render",
        "POST",
        "https://api.render.com/v1/services",
        "token-123456",
        payload={
            "name": "site-pessoal-homolog",
            "repo": "https://github.com/a-castilho/site-pessoal.git",
        },
    )

    assert result == {"ok": True}
    assert captured["payload"]["repo"] == "https://github.com/a-castilho/site-pessoal"
