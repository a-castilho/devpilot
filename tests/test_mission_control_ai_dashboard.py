from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSION_CONTROL = ROOT / "app" / "static" / "mission-control.js"
AI_DASHBOARD = ROOT / "app" / "static" / "mission-control-ai-dashboard.js"
AI_DASHBOARD_CSS = ROOT / "app" / "static" / "mission-control-ai-dashboard.css"
FEATURE_LOADER = ROOT / "app" / "static" / "feature-loader.js"


def test_mission_control_loads_ai_dashboard_extension():
    source = MISSION_CONTROL.read_text(encoding="utf-8")
    assert "mission-control-ai-dashboard.js" in source
    assert "ensureEnhancements()" in source


def test_ai_chat_launchers_delegate_to_single_canonical_chat():
    source = AI_DASHBOARD.read_text(encoding="utf-8")
    assert "mc-ai-launcher" in source
    assert "mc-ai-header-button" in source
    assert "openCanonicalChat" in source
    assert "window.devpilotOpenChat" in source

    # Mission Control não pode voltar a manter uma segunda implementação de chat.
    assert "mc-ai-drawer" not in source
    assert "api('/chat'" not in source
    assert "data-mc-ai-mode" not in source
    assert "chatHistory" not in source


def test_chat_opens_on_first_click_before_lazy_features_finish_loading():
    source = FEATURE_LOADER.read_text(encoding="utf-8")
    assert "window.devpilotOpenChat = openChat" in source

    start = source.index("function openChat()")
    end = source.index("window.devpilotOpenChat = openChat", start)
    block = source[start:end]
    assert "modal && !modal.open" in block
    assert block.index("modal.showModal") < block.index("loadFeature('voice')")
    assert "window.loadProjects" in block

    click_start = source.index("if (feature === 'voice')")
    click_end = source.index("if (trigger.dataset.devpilotFeatureReplay", click_start)
    click_block = source[click_start:click_end]
    assert "event.stopImmediatePropagation()" in click_block
    assert "void openChat()" in click_block
    assert "trigger.click()" not in click_block


def test_mission_control_prefers_visual_charts_and_responsive_layout():
    source = AI_DASHBOARD.read_text(encoding="utf-8")
    styles = AI_DASHBOARD_CSS.read_text(encoding="utf-8")
    assert "mc-chart-grid" in source
    assert "mc-donut" in source
    assert "mc-stacked-chart" in source
    assert "mc-chart-line" in source
    assert "@media (max-width: 640px)" in styles
    assert "grid-template-columns: minmax(0, 1fr)" in styles
