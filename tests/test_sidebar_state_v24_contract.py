from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_state_v24_contract():
    css = (ROOT / "app/static/sidebar-state-v24.css").read_text(encoding="utf-8")
    viewport = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")

    assert "DevPilot Sidebar State V24" in css
    assert "html.sidebar-collapsed .shell" in css
    assert "html:not(.sidebar-collapsed) .shell" in css
    assert "--dp-sidebar-v24-open" in css
    assert "--dp-sidebar-v24-closed: 72px" in css
    assert "font-size: 0 !important" in css
    assert "nav-group-label" in css
    assert "sidebar-search" in css
    assert "system-card" in css
    assert "sidebar-state-v24.css" in viewport
    assert "data-sidebar-state-v24" in viewport


if __name__ == "__main__":
    test_sidebar_state_v24_contract()
    print("SIDEBAR V24: contrato OK")
