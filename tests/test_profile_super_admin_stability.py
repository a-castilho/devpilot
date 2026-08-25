from pathlib import Path


PROFILE = Path("app/static/profile.js")


def test_profile_reuses_authenticated_user_and_avoids_boot_fetch():
    source = PROFILE.read_text(encoding="utf-8")
    assert "state?.currentUser" in source
    assert "if (initialUser) render(initialUser);" in source
    assert "loadProfile({silent:true})" not in source


def test_profile_deduplicates_me_requests():
    source = PROFILE.read_text(encoding="utf-8")
    assert "let profileRequest = null;" in source
    assert "if (profileRequest) return profileRequest;" in source
    assert "profileRequest = null" in source


def test_profile_navigation_does_not_hijack_development_view():
    source = PROFILE.read_text(encoding="utf-8")
    assert "item.dataset.view === 'profile'" in source
    assert "view.id === 'profile-view'" in source
    assert "showView('tasks')" not in source
