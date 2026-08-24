from pathlib import Path

from app.main import STATIC, spa


def test_profile_runtime_is_loaded_once():
    rendered = spa("profile").body.decode("utf-8")

    assert rendered.count("/assets/profile.js?v=") == 1


def test_profile_ui_survives_view_remounts():
    script = Path(STATIC / "profile.js").read_text(encoding="utf-8")

    assert "nav.dataset.view = 'profile'" in script
    assert "function ensureProfileMounted()" in script
    assert "return section.querySelector('#profile-form')" in script
    assert "form.elements.namedItem(k)" in script
    assert "if (!form) throw new Error" in script
