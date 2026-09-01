from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/game-operations-v39.css").read_text(encoding="utf-8")


def test_new_project_view_is_supported_by_central_navigation():
    assert "'new-project': 'Novo projeto'" in NAV
    assert "installVisibilitySafeShowView" in NAV
    assert "markOnlyView(viewName)" in NAV
    assert "restoreViewVisibility(viewName)" in NAV
    assert "view.hidden = !active" in NAV


def test_game_style_is_loaded_by_authenticated_navigation():
    assert "ensureGameUiStyles" in NAV
    assert "devpilot-game-operations-v39" in NAV
    assert "/assets/game-operations-v39.css?v=20260901-1" in NAV


def test_projects_do_not_render_duplicate_new_project_cta():
    assert "#projects-view:has([data-project-builder-open]) .projects-new-project-sticky" in CSS
    assert "display:none !important" in CSS


def test_projects_and_builder_have_game_hud_contract():
    for token in (
        "FROTA DE PROJETOS",
        "HANGAR · CONFIGURAÇÃO DA NAVE",
        "LANÇAMENTO · ",
        "#projects-list .project-card",
        "#new-project-view .choice-card.selected",
    ):
        assert token in CSS


def test_executions_are_presented_as_game_missions():
    for token in (
        "CENTRAL DE MISSÕES · TEMPO REAL",
        "RADAR DE MISSÕES",
        "MISSÃO",
        "LOG DA MISSÃO",
        "#tasks-view .tasks-v9-row:has(.tasks-v9-status.failed)",
        "#tasks-view .tasks-v9-actions button",
    ):
        assert token in CSS


def test_game_layout_keeps_mobile_and_reduced_motion_support():
    assert "@media (max-width:900px)" in CSS
    assert "@media (max-width:520px)" in CSS
    assert "@media (prefers-reduced-motion:reduce)" in CSS
