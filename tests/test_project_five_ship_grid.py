from pathlib import Path


STYLES = Path("app/static/project-card-scroll.css")


def test_desktop_projects_grid_uses_exactly_five_columns():
    source = STYLES.read_text(encoding="utf-8")

    assert "@media (min-width: 901px)" in source
    assert "#projects-view #projects-list.cards" in source
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in source
