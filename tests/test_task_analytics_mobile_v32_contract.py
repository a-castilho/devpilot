from pathlib import Path


CSS = Path("app/static/task-analytics.css")


def test_mobile_analytics_v32_uses_full_width_single_column():
    source = CSS.read_text(encoding="utf-8")

    assert "DevPilot V32" in source
    assert "body #tasks-view > .task-analytics > .task-charts-grid" in source
    assert "grid-template-columns: minmax(0, 1fr) !important" in source
    assert "overflow-x: visible !important" in source
    assert "scroll-snap-type: none !important" in source
    assert "body #tasks-view .task-chart-wide" in source
    assert "width: 100% !important" in source
    assert "scroll-snap-align: none !important" in source


def test_mobile_analytics_v32_keeps_priority_cards_readable():
    source = CSS.read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(3, minmax(0, 1fr)) !important" in source
    assert "overflow-wrap: anywhere !important" in source
