import pytest
from fastapi import HTTPException
from starlette.requests import Request

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
