from pathlib import Path


LAYOUT_CONTRACT = Path("app/static/layout-contract.css")
MOBILE_MENU_CSS = Path("app/static/mobile-accordion-menu.css")
WORKFLOW_UI = Path("app/static/task-workflow-observability.js")


def test_layout_contract_is_loaded_after_legacy_dashboard_foundation():
    css = MOBILE_MENU_CSS.read_text(encoding="utf-8")

    dashboard_import = "@import url('/assets/dashboard-layout-v2.css?v=20260829-1');"
    contract_import = "@import url('/assets/layout-contract.css?v=20260829-1');"

    assert dashboard_import in css
    assert contract_import in css
    assert css.index(dashboard_import) < css.index(contract_import)


def test_compact_desktop_task_table_scrolls_internally_instead_of_crushing_columns():
    css = LAYOUT_CONTRACT.read_text(encoding="utf-8")
    compact = css.split("@media (min-width: 901px) and (max-width: 1180px)", 1)[1]

    assert "overflow-x: auto !important" in compact
    assert "min-width: 980px !important" in compact
    assert "table-layout: auto !important" in compact
    assert "white-space: nowrap !important" in compact
    assert "overflow-wrap: normal !important" in compact
    assert "table-layout: fixed !important" not in compact
    assert "overflow-x: hidden !important" not in compact


def test_compact_desktop_does_not_assume_runtime_task_table_has_only_five_columns():
    css = LAYOUT_CONTRACT.read_text(encoding="utf-8")
    workflow = WORKFLOW_UI.read_text(encoding="utf-8")

    assert "data-task-flow-header" in workflow
    assert "task-flow-cell" in workflow
    assert "th[data-task-flow-header]" in css
    assert "td.task-flow-cell" in css
    assert "min-width: 150px !important" in css


def test_mobile_runtime_flow_column_receives_a_semantic_label():
    css = LAYOUT_CONTRACT.read_text(encoding="utf-8")

    assert "@media (max-width: 900px)" in css
    assert "td.task-flow-cell::before" in css
    assert "content: 'Fluxo' !important" in css


def test_global_layout_contract_keeps_shared_surfaces_shrinkable_and_actions_readable():
    css = LAYOUT_CONTRACT.read_text(encoding="utf-8")

    for selector in (
        ".shell",
        "main",
        ".view",
        ".panel",
        ".table-wrap",
        ".project-builder",
        ".reports-grid",
        ".header-actions",
    ):
        assert selector in css

    assert "min-width: 0" in css
    assert ".table-wrap th" in css
    assert "word-break: normal !important" in css
    assert ".header-actions button" in css
    assert "white-space: nowrap" in css
