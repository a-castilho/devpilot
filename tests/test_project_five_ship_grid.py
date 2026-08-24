from pathlib import Path


STYLES = Path("app/static/project-card-scroll.css")


def test_desktop_projects_grid_uses_exactly_five_columns():
    source = STYLES.read_text(encoding="utf-8")

    assert "@media (min-width: 901px)" in source
    assert "#projects-view #projects-list.cards" in source
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in source


def test_ship_commands_wrap_instead_of_disappearing_in_five_column_grid():
    source = STYLES.read_text(encoding="utf-8")

    assert ".project-card.project-ship-card > .list-row" in source
    assert "flex-direction: column;" in source
    assert "> div:not(.project-status-strip)" in source
    assert "flex-wrap: wrap;" in source
    assert "flex: 1 1 30px;" in source
    assert "[data-project-weapons]" in source
    assert "content: '⚔';" in source
