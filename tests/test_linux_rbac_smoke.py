from pathlib import Path

from app.security import Role, can_manage_role


ROOT = Path(__file__).resolve().parents[1]


def test_linux_rbac_root_is_not_delegable_in_user_editor():
    users_js = (ROOT / "app/static/users.js").read_text(encoding="utf-8")
    assert "requested === 'SUPER_ADMIN'" in users_js
    assert "Perfil não atribuível nesta sessão" in users_js
    assert "data-user-role-save" in users_js


def test_linux_rbac_operational_matrix_remains_least_privilege():
    assert can_manage_role(Role.OWNER, Role.ADMIN)
    assert can_manage_role(Role.ADMIN, Role.ANALYST)
    assert not can_manage_role(Role.ADMIN, Role.OWNER)
    assert not can_manage_role(Role.ANALYST, Role.ADMIN)
