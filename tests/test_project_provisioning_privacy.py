from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.project_provisioning_routes as provisioning_routes
from app.project_provisioning_routes import (
    GENERIC_PROJECT_CREATE_ERROR,
    provisioning_client_error,
)
from app.security import Principal, Role, require_access
from app.services.github_provisioning import GitHubProvisioningError


def principal(role: Role) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id="workspace-1",
        email="user@example.com",
        role=role,
    )


def request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def test_regular_user_never_receives_github_credential_details():
    error = GitHubProvisioningError(
        "Fine-grained PAT sem Administration: Read and write",
        403,
    )

    result = provisioning_client_error(principal(Role.OWNER), error)

    assert result.status_code == 503
    assert result.detail == GENERIC_PROJECT_CREATE_ERROR
    assert "PAT" not in str(result.detail)
    assert "GitHub" not in str(result.detail)


def test_regular_user_never_receives_internal_organization_configuration_details():
    error = HTTPException(
        status_code=409,
        detail="A credencial GitHub da organização está desativada.",
    )

    result = provisioning_client_error(principal(Role.ADMIN), error)

    assert result.status_code == 503
    assert result.detail == GENERIC_PROJECT_CREATE_ERROR


def test_super_admin_keeps_diagnostic_github_details():
    error = GitHubProvisioningError(
        "Fine-grained PAT sem Administration: Read and write",
        403,
    )

    result = provisioning_client_error(principal(Role.SUPER_ADMIN), error)

    assert result.status_code == 403
    assert "Fine-grained PAT" in str(result.detail)


def test_super_admin_keeps_internal_configuration_error():
    error = HTTPException(
        status_code=409,
        detail="A credencial GitHub da organização está desativada.",
    )

    result = provisioning_client_error(principal(Role.SUPER_ADMIN), error)

    assert result is error


def test_regular_user_cannot_use_manual_project_repository_endpoint():
    with pytest.raises(HTTPException) as captured:
        require_access(request("POST", "/api/projects"), principal(Role.OWNER))

    assert captured.value.status_code == 403


def test_regular_user_can_use_automatic_project_provisioning_endpoint():
    actor = require_access(request("POST", "/api/projects/provision"), principal(Role.OWNER))

    assert actor == "user:user-1"


def test_super_admin_keeps_manual_project_repository_option():
    actor = require_access(request("POST", "/api/projects"), principal(Role.SUPER_ADMIN))

    assert actor == "user:user-1"


def test_regular_user_keeps_project_when_github_provisioning_fails(monkeypatch):
    db = SimpleNamespace(scalar=lambda _statement: None)
    ws = SimpleNamespace(id="workspace-1")
    organization = SimpleNamespace(id="organization-1")
    persisted_project = object()
    persisted = {}

    monkeypatch.setattr(provisioning_routes, "workspace", lambda _db: ws)
    monkeypatch.setattr(
        provisioning_routes,
        "authorized_organization",
        lambda _db, _workspace_id: organization,
    )
    monkeypatch.setattr(
        provisioning_routes,
        "organization_access_token",
        lambda _db, _workspace_id, _organization: "secret-token",
    )

    def fail_github(*_args, **_kwargs):
        raise GitHubProvisioningError("detalhe interno do provedor", 403)

    monkeypatch.setattr(provisioning_routes, "create_github_repository", fail_github)
    monkeypatch.setattr(provisioning_routes, "record", lambda *_args, **_kwargs: None)

    def persist_fallback(_db, **kwargs):
        persisted.update(kwargs)
        return persisted_project

    monkeypatch.setattr(provisioning_routes, "persist_deferred_project", persist_fallback)

    payload = provisioning_routes.ProjectProvisionCreate(
        name="André Tonal",
        slug="andre-tonal",
        description="Site musical",
        agents_md="# AGENTS.md",
        codex_config={"project_blueprint": {"project_type": ["landing-page"]}},
    )

    result = provisioning_routes.provision_project(
        payload,
        db=db,
        principal=principal(Role.OWNER),
        actor="user:user-1",
    )

    assert result is persisted_project
    assert persisted["organization"] is organization
    assert persisted["source"] == "automatic_provision_fallback"
    assert persisted["slug"] == "andre-tonal"
    assert persisted["codex_config"] == payload.codex_config
