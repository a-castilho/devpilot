from fastapi import HTTPException

from app.project_provisioning_routes import (
    GENERIC_PROJECT_CREATE_ERROR,
    provisioning_client_error,
)
from app.security import Principal, Role
from app.services.github_provisioning import GitHubProvisioningError


def principal(role: Role) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id="workspace-1",
        email="user@example.com",
        role=role,
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
