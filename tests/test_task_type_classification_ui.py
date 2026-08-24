from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_task_type_column_enhances_active_and_legacy_renderers():
    script = read("app/static/task-modal.js")

    assert "tr.task-main-row, tr[data-task-id]" in script
    assert "row.dataset.taskId" in script
    assert "task-kind-cell" in script
    assert "header.textContent = 'Tipo'" in script
    assert "emptyCell.colSpan" in script


def test_task_type_classifier_exposes_semantic_labels():
    script = read("app/static/task-modal.js")

    for label in (
        "Correção",
        "Validação",
        "Revisão",
        "Análise",
        "Desenvolvimento",
        "Jogo",
        "Deploy",
        "Execução",
        "Outro",
    ):
        assert f"'{label}'" in script

    assert "[devpilot_stage=correct]" in script
    assert "[post-execution-verification]" in script
    assert "[devpilot_build_game_v1]" in script
    assert "marker === 'fix'" in script
    assert "marker === 'develop'" in script


def test_task_analytics_uses_same_semantic_task_types():
    script = read("app/static/task-analytics.js")

    assert "<h3>Tipos de tarefa</h3>" in script
    assert "return 'Correção'" in script
    assert "return 'Validação'" in script
    assert "return 'Revisão'" in script
    assert "return 'Análise'" in script
    assert "return 'Desenvolvimento'" in script
    assert "return 'Jogo'" in script
    assert "return 'Deploy'" in script
    assert "return 'Execução'" in script
    assert "'Outro'" in script
