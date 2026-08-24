from pathlib import Path
from types import SimpleNamespace

from app.worker import (
    _analysis_action_priority,
    _analysis_action_prompt,
    _analysis_action_title,
    _is_analysis_task,
)


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_analysis_task_generates_action_without_recursive_analysis_classification():
    analysis = SimpleNamespace(
        title="Análise técnica de Site pessoal",
        prompt="Faça uma auditoria somente leitura do projeto. Não modifique arquivos.",
        source="dashboard",
    )
    action = SimpleNamespace(
        title="Ação recomendada · Site pessoal",
        prompt="[analysis-action]\n[analysis-run:run-1]\nImplemente os achados da análise.",
        source="analysis",
    )

    assert _is_analysis_task(analysis) is True
    assert _is_analysis_task(action) is False


def test_explicit_analysis_and_execution_modes_are_not_confused():
    analysis = SimpleNamespace(
        title="Revisão",
        prompt="[DEVPILOT_MODE=analysis-read-only]\nInvestigue sem alterar arquivos.",
        source="dashboard",
    )
    execution = SimpleNamespace(
        title="Correção",
        prompt="[DEVPILOT_MODE=fix]\nCorrija o problema.",
        source="dashboard",
    )

    assert _is_analysis_task(analysis) is True
    assert _is_analysis_task(execution) is False


def test_generated_action_has_action_title_marker_and_priority():
    project = SimpleNamespace(name="Site pessoal")
    run = SimpleNamespace(id="run-123")
    report = "Risco crítico de segurança encontrado."

    title = _analysis_action_title(project)
    prompt = _analysis_action_prompt(run, report)

    assert title == "Ação recomendada · Site pessoal"
    assert "análise" not in title.lower()
    assert "[analysis-action]" in prompt
    assert "[analysis-run:run-123]" in prompt
    assert "Não faça uma nova análise" in prompt
    assert _analysis_action_priority(report) == 90


def test_mobile_task_columns_match_injected_type_column():
    modal = read("app/static/task-modal.js")
    analytics = read("app/static/task-analytics.js")
    styles = read("app/static/task-analytics.css")

    assert "return 'action'" in modal
    assert "kind === 'action' ? 'Ação'" in modal
    assert "return 'Ação'" in analytics
    assert "content:'Tipo'" in styles
    assert "td:nth-child(4)::before{content:'Status'}" in styles
    assert "td:nth-child(5)::before{content:'Prioridade'}" in styles
    assert "td:nth-child(6)::before{content:'Ação'}" in styles
