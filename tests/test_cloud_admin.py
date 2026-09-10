import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.cloud_admin_routes import (
    CloudCredentialUpdate,
    _provider_request,
    list_clouds,
    manage_clouds,
    save_cloud,
)
from app.db import Base
from app.models import Organization, ProviderCredential, Workspace
from app.security import Principal, Role
from app.services.vault import Vault


@pytest.fixture
def clouds_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        other = Workspace(name="Other", slug="other")
        db.add_all([workspace, other])
        db.commit()
        yield db, workspace, other
    engine.dispose()


def principal(workspace: Workspace, role: Role = Role.SUPER_ADMIN) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id=workspace.id,
        email="root@example.com",
        role=role,
    )


def test_cloud_admin_is_super_admin_only(clouds_db):
    _, workspace, _ = clouds_db
    with pytest.raises(HTTPException) as error:
        manage_clouds(principal(workspace, Role.ADMIN))

    assert error.value.status_code == 403


def test_cloud_token_is_encrypted_and_never_returned(clouds_db):
    db, workspace, _ = clouds_db
    token = "vercel-secret-token-123456"
    result = save_cloud(
        "vercel",
        CloudCredentialUpdate(secret=token, enabled=True, scope="team_example"),
        db=db,
        principal=principal(workspace),
    )

    stored = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace.id,
            ProviderCredential.provider == "cloud:vercel",
        )
    )
    assert stored is not None
    assert stored.encrypted_secret != token
    assert Vault().decrypt(stored.encrypted_secret) == token
    assert result["configured"] is True
    assert result["scope"] == "team_example"
    assert "secret" not in result
    assert "encrypted_secret" not in result


def test_cloud_credentials_are_workspace_isolated(clouds_db):
    db, workspace, other = clouds_db
    db.add(
        ProviderCredential(
            workspace_id=other.id,
            provider="cloud:render",
            label="cloud-admin",
            encrypted_secret=Vault().encrypt("render-secret-token-123"),
            models='{"scope":"owner-other"}',
            enabled=True,
        )
    )
    db.commit()

    items = list_clouds(db=db, principal=principal(workspace))
    render = next(item for item in items if item["provider"] == "render")

    assert render["configured"] is False
    assert render["scope"] == ""


def test_github_cloud_save_updates_linked_organization_credential(clouds_db):
    db, workspace, _ = clouds_db
    organization = Organization(
        workspace_id=workspace.id,
        provider="github",
        name="A Castilho",
        slug="a-castilho",
        external_login="a-castilho",
    )
    db.add(organization)
    db.commit()

    token = "github-cloud-token-latest-123456"
    save_cloud(
        "github",
        CloudCredentialUpdate(secret=token, enabled=True, scope=""),
        db=db,
        principal=principal(workspace),
    )
    db.refresh(organization)

    assert organization.credential_id
    linked = db.scalar(
        select(ProviderCredential).where(ProviderCredential.id == organization.credential_id)
    )
    assert linked is not None
    assert linked.provider == "github"
    assert linked.enabled is True
    assert Vault().decrypt(linked.encrypted_secret) == token


def test_github_cloud_existing_secret_is_reused_for_organization_sync(clouds_db):
    db, workspace, _ = clouds_db
    cloud = ProviderCredential(
        workspace_id=workspace.id,
        provider="cloud:github",
        label="cloud-admin",
        encrypted_secret=Vault().encrypt("github-existing-cloud-token-123456"),
        models='{"scope":"","credential_source":"manual"}',
        enabled=True,
    )
    organization = Organization(
        workspace_id=workspace.id,
        provider="github",
        name="A Castilho",
        slug="a-castilho",
        external_login="a-castilho",
    )
    db.add_all([cloud, organization])
    db.commit()

    list_clouds(db=db, principal=principal(workspace))
    db.refresh(organization)

    linked = db.scalar(
        select(ProviderCredential).where(ProviderCredential.id == organization.credential_id)
    )
    assert linked is not None
    assert Vault().decrypt(linked.encrypted_secret) == "github-existing-cloud-token-123456"


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_vercel_team_id_scope_is_sent_as_team_id(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"projects": []})

    monkeypatch.setattr("app.cloud_admin_routes.httpx.get", fake_get)

    _provider_request("vercel", "token-123456", "team_example", resources=True)

    assert calls[0][0] == "https://api.vercel.com/v9/projects"
    assert calls[0][1]["params"]["teamId"] == "team_example"
    assert "slug" not in calls[0][1]["params"]


def test_vercel_slug_scope_is_sent_as_slug_and_validated_on_test(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"projects": []})

    monkeypatch.setattr("app.cloud_admin_routes.httpx.get", fake_get)

    _provider_request("vercel", "token-123456", "maquina-de-leads1", resources=False)

    assert calls[0][0] == "https://api.vercel.com/v9/projects"
    assert calls[0][1]["params"]["slug"] == "maquina-de-leads1"
    assert calls[0][1]["params"]["limit"] == 1


def test_neon_organization_scope_is_sent_as_org_id(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"projects": []})

    monkeypatch.setattr("app.cloud_admin_routes.httpx.get", fake_get)

    _provider_request("neon", "token-123456", "org-example", resources=True)

    assert calls[0][0] == "https://console.neon.tech/api/v2/projects"
    assert calls[0][1]["params"]["org_id"] == "org-example"


def test_github_organization_scope_is_url_encoded_and_validated(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"organization": {"login": "a-castilho"}})

    monkeypatch.setattr("app.cloud_admin_routes.httpx.get", fake_get)

    _provider_request("github", "token-123456", "a-castilho", resources=False)

    assert calls[0][0] == "https://api.github.com/user/memberships/orgs/a-castilho"
