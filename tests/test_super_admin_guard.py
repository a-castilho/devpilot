import pytest
from fastapi import HTTPException

from app.security import Principal, Role, require_super_admin


def principal(role: Role) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id="workspace-1",
        email="user@example.com",
        role=role,
    )


def test_super_admin_guard_allows_super_admin():
    assert require_super_admin(principal(Role.SUPER_ADMIN)) == "user:user-1"


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.ANALYST, Role.VIEWER])
def test_super_admin_guard_rejects_every_other_role(role):
    with pytest.raises(HTTPException) as caught:
        require_super_admin(principal(role))
    assert caught.value.status_code == 403
    assert caught.value.detail == "Acesso exclusivo do Super Admin"
