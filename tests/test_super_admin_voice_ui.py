from pathlib import Path

from app.main import STATIC, spa


def test_super_admin_voice_asset_is_lazy_loaded_by_feature_loader():
    response = spa("voice-admin")
    rendered = response.body.decode("utf-8")
    loader = Path(STATIC / "feature-loader.js").read_text(encoding="utf-8")

    assert "/assets/super-admin-voice.js?v=" not in rendered
    assert "'super-admin-voice.js'" in loader
    assert "voice: [" in loader
    assert "/assets/super-admin-voice.css?v=" in rendered


def test_super_admin_voice_repairs_partial_shell_and_stays_in_admin_group():
    script = Path(STATIC / "super-admin-voice.js").read_text(encoding="utf-8")

    assert "function ensureSection(main = document.querySelector('main'))" in script
    assert "#voice-admin-view" in script
    assert "section.parentElement !== main" in script
    assert "button.dataset.superAdmin = 'true'" in script
    assert "button.dataset.navGroup = 'super-admin'" in script
    assert "button.classList.contains('active') || section.classList.contains('active')" in script


def test_super_admin_voice_remounts_view_before_every_activation():
    script = Path(STATIC / "super-admin-voice.js").read_text(encoding="utf-8")

    assert "function activate(button)" in script
    assert "const section = ensureSection();" in script
    assert "button.addEventListener('click', () => activate(button))" in script
    assert "bindSectionControls(section)" in script


def test_super_admin_voice_has_visible_loading_and_retry_states():
    script = Path(STATIC / "super-admin-voice.js").read_text(encoding="utf-8")

    assert "Carregando diagnóstico de voz" in script
    assert "Não foi possível carregar a administração de voz" in script
    assert "voice-admin-retry" in script
    assert "Tentar novamente" in script
    assert "cache: 'no-store'" in script


def test_super_admin_voice_has_operational_charts_and_connection_management():
    script = Path(STATIC / "super-admin-voice.js").read_text(encoding="utf-8")
    styles = Path(STATIC / "super-admin-voice.css").read_text(encoding="utf-8")

    assert "renderUsageChart" in script
    assert "renderOutcomeChart" in script
    assert "voice-admin-donut" in script
    assert "voice-admin-bar-track" in script
    assert "GERENCIAMENTO" in script
    assert "/enabled`" in script
    assert "/models`" in script
    assert "method: 'DELETE'" in script
    assert "Salvar alterações" in script
    assert ".voice-admin-view{width:100%!important;max-width:none!important" in styles
    assert ".voice-admin-charts" in styles
    assert "@media(max-width:760px)" in styles
