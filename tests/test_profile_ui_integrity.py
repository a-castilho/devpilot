from pathlib import Path

from app.main import STATIC, spa


FEATURE_LOADER = Path(STATIC / "feature-loader.js")


def test_profile_runtime_is_lazy_owned_by_feature_loader():
    rendered = spa("profile").body.decode("utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "/assets/profile.js?v=" not in rendered
    assert "profile: ['profile.js']" in loader
    assert "addPlaceholder('profile', 'Perfil')" in loader


def test_profile_ui_can_mount_idempotently():
    script = Path(STATIC / "profile.js").read_text(encoding="utf-8")

    assert "nav.dataset.view = 'profile'" in script
    assert "function mount()" in script
    assert "if (!nav.isConnected" in script
    assert "if (!section.isConnected" in script
    assert "document.querySelector('#profile-view')" in script


def test_profile_save_uses_delegated_submit_after_remount():
    script = Path(STATIC / "profile.js").read_text(encoding="utf-8")

    assert "document.addEventListener('submit'" in script
    assert "form.id !== 'profile-form'" in script
    assert "saveProfile(form)" in script
    assert "method:'PATCH'" in script
    assert "'/api/auth/me'" in script


def test_global_refresh_reloads_active_profile():
    script = Path(STATIC / "profile.js").read_text(encoding="utf-8")

    assert "document.querySelector('#refresh')?.addEventListener('click'" in script
    assert "section.classList.contains('active')" in script
    assert "window.devpilotRefreshProfile = options => loadProfile" in script
    assert "force:Boolean(options?.force)" in script
