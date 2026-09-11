from pathlib import Path

MENU = Path("app/static/mobile-accordion-menu.js")


def test_mobile_shell_has_no_dynamic_script_loader():
    source = MENU.read_text(encoding="utf-8")
    assert "document.createElement('script')" not in source
    assert "mobile-page-back.js" not in source


def test_mobile_keeps_one_primary_cta_and_accordions():
    source = MENU.read_text(encoding="utf-8")
    assert "mobile-primary-cta" in source
    assert "mobile-control-accordion" in source
    assert "Ações do sistema" in source
    assert "Filtros e busca" in source
    assert "Indicadores" in source
    assert "Frota de projetos" in source
    assert "preferredPrimary" in source
    assert "dp-mobile-source-hidden" in source


def test_actions_are_preserved_through_proxy_clicks_instead_of_removed():
    source = MENU.read_text(encoding="utf-8")
    assert "source?.click()" in source
    assert "collectActionSources" in source
    assert "cloneNode(true)" in source
    assert ".remove()" in source  # only generated shells are replaced; source controls remain in DOM


def test_projects_and_tasks_choose_the_expected_green_cta():
    source = MENU.read_text(encoding="utf-8")
    assert "view.id === 'projects-view'" in source
    assert "[data-project-builder-open]" in source
    assert "view.id === 'tasks-view'" in source
    assert ".tasks-v9-toolbar .primary[data-open=\"task-modal\"]" in source
    assert "view.id === 'overview-view'" in source
    assert ".overview-actions .primary[data-open=\"task-modal\"]" in source


def test_internal_mobile_view_still_opens_at_top_and_keeps_back_navigation():
    source = MENU.read_text(encoding="utf-8")
    assert "const BACK_CLASS = 'mobile-page-back'" in source
    assert "position:sticky" in source
    assert "window.scrollTo({top:0" in source
    assert "devpilot:view-changed" in source
    assert ".nav[data-view=" in source
