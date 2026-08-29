from pathlib import Path


DASHBOARD_HTML = Path("app/static/index.html")
DASHBOARD_CSS = Path("app/static/dashboard-layout-v2.css")
MOBILE_MENU_CSS = Path("app/static/mobile-accordion-menu.css")


def test_overview_primary_cta_opens_project_builder_not_task_modal():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert '<button class="primary" type="button" data-project-builder-open>Criar projeto</button>' in html
    assert 'data-open="task-modal">Criar desenvolvimento</button>' not in html


def test_dashboard_v2_is_loaded_from_existing_layout_stack():
    mobile_css = MOBILE_MENU_CSS.read_text(encoding="utf-8")

    assert mobile_css.startswith("@import url('/assets/dashboard-layout-v2.css?v=20260829-1');")


def test_dashboard_v3_normalizes_primary_surfaces_and_main_geometry():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    for selector in (
        ".view",
        ".cards",
        ".panel",
        ".project-card",
        ".builder-card",
        ".table-wrap",
        ".reports-grid",
        ".task-analytics",
    ):
        assert selector in css

    assert "--dashboard-content:1600px" in css
    assert "padding:0!important" in css
    assert "overflow-x:auto" in css
    assert "grid-template-columns:var(--dp-sidebar-desktop) minmax(0,1fr)" in css


def test_compact_desktop_uses_icon_rail_instead_of_wide_sidebar():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "@media (min-width:901px) and (max-width:1180px)" in css
    assert "--dp-sidebar-compact:78px" in css
    assert "grid-template-columns:var(--dp-sidebar-compact) minmax(0,1fr)!important" in css
    assert "width:var(--dp-sidebar-compact)!important" in css
    assert ".sidebar-collapse-toggle" in css
    assert "display:none!important" in css


def test_compact_desktop_restores_real_five_column_task_table():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "#tasks-view .table-wrap thead { display:table-header-group!important; }" in css
    assert "#tasks-view .table-wrap tbody { display:table-row-group!important; }" in css
    assert "#tasks-view th:nth-child(5),#tasks-view td:nth-child(5)" in css
    assert "#tasks-view .table-wrap tbody tr.task-main-row>td::before" in css
    assert "content:none!important" in css


def test_mobile_task_cards_use_the_real_five_column_labels():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "td:nth-child(2)::before { content:'Origem'!important; }" in css
    assert "td:nth-child(3)::before { content:'Status'!important; }" in css
    assert "td:nth-child(4)::before { content:'Prioridade'!important; }" in css
    assert "td:nth-child(5)::before { content:'Ação'!important; }" in css
    assert "td:nth-child(6)::before" not in css


def test_mobile_uses_natural_height_cards_and_no_global_scroll_snap():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "@media (max-width:900px)" in css
    assert "scroll-snap-type:none!important" in css
    assert "min-height:auto!important" in css
    assert "#overview-view>.grid-two" in css
    assert "display:grid!important" in css


def test_dashboard_is_responsive_from_desktop_to_small_mobile():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in css
    assert "@media (max-width:900px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "@media (max-width:560px)" in css
    assert ".metrics { grid-template-columns:1fr; }" in css
    assert ".project-builder" in css
    assert "display:block!important" in css
    assert "dialog,.modal" in css
    assert "width:min(96vw,620px)!important" in css


def test_sticky_content_respects_global_header_height():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "--dp-header-height:78px" in css
    assert "top:var(--dp-header-height)" in css
    assert "top:calc(var(--dp-header-height) + 16px)!important" in css


def test_dashboard_preserves_accessibility_and_readability():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "color-scheme:dark" in css
    assert "pre {" in css
    assert "white-space:pre-wrap" in css
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "transition:none!important" in css
