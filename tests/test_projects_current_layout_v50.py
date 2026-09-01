from pathlib import Path


CSS = Path("app/static/project-card-scroll.css").read_text(encoding="utf-8")


def test_lightweight_projects_cards_do_not_create_nested_description_scroll():
    assert "overflow-y: auto" not in CSS
    assert "-webkit-line-clamp: 3" in CSS
    assert "max-height: 4.5em" in CSS


def test_lightweight_projects_actions_are_grouped_and_responsive():
    assert ".project-card .list-row > div:last-child" in CSS
    assert "flex-wrap:wrap" in CSS
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in CSS
    assert "grid-template-columns:1fr!important" in CSS


def test_ship_enhanced_layout_contract_is_preserved():
    assert "html.devpilot-project-ships-ready" in CSS
    assert "repeat(5,minmax(0,1fr)) !important" in CSS
