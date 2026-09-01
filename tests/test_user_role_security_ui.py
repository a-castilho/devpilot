from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_role_editor_never_offers_super_admin_as_assignable_role():
    source = (ROOT / "app/static/users.js").read_text(encoding="utf-8")

    assert "request('/api/users/roles')" in source
    assert "assignableRoles.has(requested)" in source
    assert "requested === 'SUPER_ADMIN'" in source
    assert "Object.keys(ROLE_LABELS)" not in source


def test_role_selection_requires_explicit_save_instead_of_mutating_on_change():
    source = (ROOT / "app/static/users.js").read_text(encoding="utf-8")

    assert "data-user-role-save" in source
    assert "Salvar perfil" in source
    assert "select.onchange" in source
    assert "save.disabled = select.value === select.dataset.originalRole" in source
    assert "select.onchange = () => updateUser" not in source


def test_owner_changes_require_masked_step_up_password():
    source = (ROOT / "app/static/users.js").read_text(encoding="utf-8")

    assert 'type="password"' in source
    assert "askStepUp" in source
    assert "confirmation_password" in source
    assert "requested === 'OWNER' || user.role === 'OWNER'" in source
    assert "Conta raiz protegida" in source
