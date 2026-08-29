from pathlib import Path


DASHBOARD_CSS = Path("app/static/dashboard-layout-v2.css")
MOBILE_MENU_CSS = Path("app/static/mobile-accordion-menu.css")
MOBILE_HOTFIX_CSS = Path("app/static/mobile-hotfix.css")
WORKFLOW_UI = Path("app/static/task-workflow-observability.js")


def test_dashboard_v2_is_loaded_from_existing_layout_stack():
    mobile_css = MOBILE_MENU_CSS.read_text(encoding="utf-8")

    assert mobile_css.startswith("@import url('/assets/dashboard-layout-v2.css?v=20260829-1');")


def test_dashboard_v4_normalizes_primary_surfaces_and_main_geometry():
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


def test_legacy_mobile_hotfix_no_longer_owns_compact_desktop_geometry():
    css = MOBILE_HOTFIX_CSS.read_text(encoding="utf-8")

    assert "Desktop/tablet geometry is owned by dashboard-layout-v2.css." in css
    assert "@media (min-width: 901px) and (max-width: 1180px)" not in css
    assert "table-layout: fixed !important" not in css


def test_compact_desktop_task_table_scrolls_internally_without_crushing_columns():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")
    compact = css.split("@media (min-width:901px) and (max-width:1180px)", 1)[1].split(
        "@media (max-width:900px)", 1
    )[0]
    task_rules = compact.split("/* Keep task columns readable.", 1)[1]

    assert "#tasks-view .panel.table-wrap" in task_rules
    assert "overflow-x:auto!important" in task_rules
    assert "min-width:980px!important" in task_rules
    assert "table-layout:auto!important" in task_rules
    assert "white-space:nowrap!important" in task_rules
    assert "overflow-wrap:normal!important" in task_rules
    assert "table-layout:fixed!important" not in task_rules
    assert "overflow-x:hidden!important" not in task_rules
    assert "#tasks-view .table-wrap tbody tr.task-main-row>td::before" in task_rules
    assert "content:none!important" in task_rules


def test_compact_desktop_supports_runtime_added_flow_column():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")
    workflow = WORKFLOW_UI.read_text(encoding="utf-8")

    assert "data-task-flow-header" in workflow
    assert "task-flow-cell" in workflow
    assert "#tasks-view .table-wrap th[data-task-flow-header]" in css
    assert "td.task-flow-cell" in css
    assert "min-width:150px!important" in css


def test_mobile_task_cards_use_base_labels_and_runtime_flow_label():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "td:nth-child(2)::before { content:'Origem'!important; }" in css
    assert "td:nth-child(3)::before { content:'Status'!important; }" in css
    assert "td:nth-child(4)::before { content:'Prioridade'!important; }" in css
    assert "td:nth-child(5)::before { content:'Ação'!important; }" in css
    assert "td.task-flow-cell::before { content:'Fluxo'!important; }" in css
    assert "#tasks-view .task-workflow-row" in css


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


def test_header_and_table_controls_keep_readable_words():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "flex-wrap:wrap" in css
    assert "word-break:normal" in css
    assert "overflow-wrap:normal" in css
    assert ".table-wrap button,.table-wrap .link,.table-wrap a { white-space:nowrap; }" in css
    assert "th {" in css
    assert "white-space:nowrap" in css


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
