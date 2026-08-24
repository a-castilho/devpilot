from pathlib import Path


SOURCE = Path("app/static/project-ships.js")


def test_projects_page_has_visual_summary_and_ring_charts():
    source = SOURCE.read_text(encoding="utf-8")

    assert "project-visual-overview" in source
    assert "conic-gradient" in source
    assert "project-visual-status-track" in source
    assert "overviewMetric('ENERGIA'" in source
    assert "overviewMetric('ESCUDO'" in source


def test_project_cards_compact_repeated_text_into_visual_status():
    source = SOURCE.read_text(encoding="utf-8")

    assert "project-verbose-copy" in source
    assert "INFRA PENDENTE" in source
    assert "OPERACIONAL" in source
    assert "project-ship-gauge" in source
    assert "grid-template-columns: repeat(3, 1fr)" in source


def test_project_actions_are_icon_first_but_accessible():
    source = SOURCE.read_text(encoding="utf-8")

    assert "project-ship-action" in source
    assert "button.setAttribute('aria-label', profile[1])" in source
    assert "button.title = profile[1]" in source
