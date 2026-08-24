from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSION_CONTROL = ROOT / "app" / "static" / "mission-control.js"
AI_DASHBOARD = ROOT / "app" / "static" / "mission-control-ai-dashboard.js"
AI_DASHBOARD_CSS = ROOT / "app" / "static" / "mission-control-ai-dashboard.css"


def test_mission_control_loads_ai_dashboard_extension():
    source = MISSION_CONTROL.read_text(encoding="utf-8")
    assert "mission-control-ai-dashboard.js" in source
    assert "ensureEnhancements()" in source


def test_ai_chat_is_always_available_and_uses_mode_aware_api():
    source = AI_DASHBOARD.read_text(encoding="utf-8")
    assert "mc-ai-launcher" in source
    assert "mc-ai-drawer" in source
    assert "api('/chat'" in source
    assert "data-mc-ai-mode=\"planning\"" in source
    assert "data-mc-ai-mode=\"build\"" in source
    assert "devpilotChatProjectContext" in source


def test_mission_control_prefers_visual_charts_and_responsive_layout():
    source = AI_DASHBOARD.read_text(encoding="utf-8")
    styles = AI_DASHBOARD_CSS.read_text(encoding="utf-8")
    assert "mc-chart-grid" in source
    assert "mc-donut" in source
    assert "mc-stacked-chart" in source
    assert "mc-chart-line" in source
    assert "@media (max-width: 640px)" in styles
    assert "grid-template-columns: minmax(0, 1fr)" in styles
