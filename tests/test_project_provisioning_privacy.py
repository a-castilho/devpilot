import json

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

import app.project_provisioning_routes as provisioning_routes
from app.models import Workspace
from app.project_provisioning_routes import (
    GENERIC_PROJECT_CREATE_ERROR,
    ProjectProvisionCreate,
    provisioning_client_error,
    provision_project,
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


class FakeProvisionSession:
    def __init__(self):
        self.workspace = Workspace(id="workspace-1", name="DevPilot", slug="default")
        self.scalar_results = [self.workspace, None]
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        return self.scalar_results.pop(0)

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


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


def test_registration_returns_before_any_github_call(monkeypatch):
    """The request transaction must not perform provider I/O; Git is queued after the response."""
    session = FakeProvisionSession()
    audit_events = []
    background_tasks = BackgroundTasks()

    monkeypatch.setattr(
        provisioning_routes,
        "record",
        lambda _db, **payload: audit_events.append(payload),
    )
    monkeypatch.setattr(
        provisioning_routes,
        "create_github_repository",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("GitHub must not run in the registration request")
        ),
    )

    project = provision_project(
        ProjectProvisionCreate(
            name="Projeto Cliente",
            slug="projeto-cliente",
            description="Cadastro sem depender da latência do GitHub",
            agents_md="# AGENTS.md",
            codex_config={"model": "gpt-5.4"},
        ),
        background_tasks=background_tasks,
        db=session,
        principal=principal(Role.OWNER),
        actor="user:user-1",
    )

    config = json.loads(project.codex_config)
    assert project.name == "Projeto Cliente"
    assert project.slug == "projeto-cliente"
    assert project.repository_url == ""
    assert project.default_branch == "main"
    assert config["repository_pending"] is True
    assert config["repository_mode"] == "deferred"
    assert config["repository_provision_state"] == "queued"
    assert session.commits == 1
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is provisioning_routes.provision_repository_in_background
    assert any(event.get("action") == "project.created_without_repository" for event in audit_events)
    assert not any(event.get("action") == "project.repository_provision" for event in audit_events)
