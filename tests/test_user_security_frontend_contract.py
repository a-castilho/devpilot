from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USERS_JS = ROOT / "app/static/users.js"


def test_user_role_change_requires_explicit_save_and_never_assigns_root():
    source = USERS_JS.read_text(encoding="utf-8")

    assert "select.onchange = () =>" in source
    assert "data-user-role-save" in source
    assert "button.onclick = () => saveRole" in source
    assert "requested === 'SUPER_ADMIN'" in source
    assert "Perfil não atribuível nesta sessão" in source


def test_step_up_password_is_masked_and_cleared_after_use():
    source = USERS_JS.read_text(encoding="utf-8")

    assert 'type="password"' in source
    assert 'autocomplete="current-password"' in source
    assert "input.value = ''" in source
    assert "confirmation_password" in source
