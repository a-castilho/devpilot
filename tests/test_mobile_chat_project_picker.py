from pathlib import Path


SOURCE = Path('app/static/mobile-accordion-menu.js').read_text(encoding='utf-8')


def test_mobile_chat_uses_custom_project_picker_instead_of_android_native_select():
    assert "mobile-chat-project-picker" in SOURCE
    assert "mobile-chat-project-trigger" in SOURCE
    assert "aria-haspopup', 'listbox" in SOURCE
    assert "pointer-events: none !important" in SOURCE
    assert "#voice-modal .voice-project-control > #voice-project" in SOURCE
    assert "select.dispatchEvent(new Event('change', {bubbles: true}))" in SOURCE


def test_mobile_chat_lazy_loads_real_projects_without_heavy_dashboard_boot():
    assert "async function ensureProjects(select)" in SOURCE
    assert "typeof loadProjects === 'function'" in SOURCE
    assert "await loadProjects()" in SOURCE
    assert "Carregando projetos…" in SOURCE
    assert "realProjects.length" in SOURCE


def test_mobile_project_picker_is_touch_and_accessibility_friendly():
    assert "min-height: 48px" in SOURCE
    assert "min-height: 46px" in SOURCE
    assert "role', 'listbox" in SOURCE
    assert "role', 'option" in SOURCE
    assert "aria-selected" in SOURCE
    assert "event.key === 'Escape'" in SOURCE
