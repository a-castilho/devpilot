from pathlib import Path


TASK_UI = Path("app/static/task-completion-documentation.js")
TASK_CSS = Path("app/static/task-development-v2.css")
DELETE_UI = Path("app/static/project-delete-ui.js")


def test_task_runtime_panel_uses_full_width_details_row():
    script = TASK_UI.read_text(encoding="utf-8")

    assert "function detailsRowFor(mainRow)" in script
    assert "function panelHostFor(mainRow, taskId)" in script
    assert "task-orchestrator-panel-host" in script
    assert "detailsRowFor(row)?.toggleAttribute('hidden', archived)" in script
    assert "mainRow?.lastElementChild" in script  # fallback only when details row is unavailable


def test_task_actions_are_grouped_and_use_distinct_action_classes():
    script = TASK_UI.read_text(encoding="utf-8")

    assert "task-orchestrator-actions" in script
    assert "task-actions-cell" in script
    assert "task-action-${action}" in script
    assert "Continuar automaticamente" in script
    assert "Arquivar" in script


def test_task_learning_is_structured_instead_of_one_long_sentence():
    script = TASK_UI.read_text(encoding="utf-8")

    assert "task-learning-grid" in script
    assert "task-learning-item" in script
    assert "['O que aconteceu', latest.happened]" in script
    assert "['Por que', latest.rationale]" in script
    assert "['Conceito', latest.concept]" in script
    assert "['Observe', latest.observe]" in script
    assert "['Aprendizado', latest.learned]" in script
    assert ".join(' · ')" not in script


def test_task_responsive_styles_are_loaded_and_keep_actions_readable():
    script = TASK_UI.read_text(encoding="utf-8")
    css = TASK_CSS.read_text(encoding="utf-8")

    assert "/assets/task-development-v2.css?v=20260829-1" in script
    assert ".task-actions-cell" in css
    assert "min-width:300px!important" in css
    assert ".task-orchestrator-actions" in css
    assert "flex-wrap:wrap" in css
    assert "white-space:nowrap!important" in css
    assert "@media (min-width:901px) and (max-width:1180px)" in css
    assert "min-width:1060px!important" in css
    assert "overflow-x:auto!important" in css
    assert "@media (max-width:560px)" in css
    assert "grid-template-columns:1fr" in css


def test_super_admin_delete_action_joins_orchestrator_action_group():
    script = DELETE_UI.read_text(encoding="utf-8")

    assert "querySelector('[data-task-orchestrator-actions]') || actionCell" in script
    assert "actions.appendChild(button)" in script
