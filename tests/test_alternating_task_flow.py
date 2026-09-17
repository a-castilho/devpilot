from pathlib import Path
from types import SimpleNamespace

from app.services.task_flow import (
    CORRECTION_STAGE_MARKER,
    IMPLEMENTATION_STAGE_MARKER,
    VERIFICATION_MARKER,
    execution_branch,
    is_analysis_action_task,
    is_analysis_task,
    is_correction_action,
    is_read_only_task,
    is_verification_analysis,
)
from app.worker import _analysis_action_prompt, _verification_analysis_prompt


ROOT = Path(__file__).resolve().parents[1]
ALTERNATING_FLOW = (ROOT / "app/services/alternating_flow.py").read_text(encoding="utf-8")


def task(*, title="", prompt="", source="dashboard", task_id="task-1"):
    return SimpleNamespace(id=task_id, title=title, prompt=prompt, source=source)


def test_legacy_correction_with_embedded_read_only_report_is_execution():
    item = task(title="Correção baseada na análise · Site pessoal", prompt="Execute as correções identificadas.\n\nDIAGNÓSTICO DE ORIGEM:\nA auditoria anterior dizia: não modifique arquivos.")
    assert is_analysis_action_task(item) is True
    assert is_analysis_task(item) is False
    assert is_read_only_task(item) is False


def test_generated_implementation_action_wins_over_analysis_text():
    run = SimpleNamespace(id="analysis-run-1")
    prompt = _analysis_action_prompt(run, "O diagnóstico foi somente leitura e dizia não modifique arquivos.")
    item = task(title="Ação recomendada · Site pessoal", prompt=prompt, source="analysis-action")
    assert IMPLEMENTATION_STAGE_MARKER in prompt
    assert is_analysis_action_task(item) is True
    assert is_read_only_task(item) is False


def test_execution_is_followed_by_read_only_verification_on_same_branch():
    run = SimpleNamespace(id="execution-run-1")
    predecessor = task(task_id="execution-task-1")
    prompt = _verification_analysis_prompt(run, predecessor, "devpilot/execution-task")
    item = task(title="Validação pós-execução · Site pessoal", prompt=prompt, source="execution-verification")
    assert VERIFICATION_MARKER in prompt
    assert is_verification_analysis(item) is True
    assert is_analysis_task(item) is True
    assert is_read_only_task(item) is True
    assert execution_branch(item) == "devpilot/execution-task"


def test_final_correction_is_execution_and_stops_the_cycle():
    run = SimpleNamespace(id="verification-run-1")
    prompt = _analysis_action_prompt(run, "Ainda existe uma regressão residual.", correction=True, target_branch="devpilot/execution-task")
    item = task(title="Correção pós-validação · Site pessoal", prompt=prompt, source="analysis-action")
    assert CORRECTION_STAGE_MARKER in prompt
    assert is_correction_action(item) is True
    assert is_analysis_action_task(item) is True
    assert is_analysis_task(item) is False
    assert is_read_only_task(item) is False
    assert execution_branch(item) == "devpilot/execution-task"


def test_missing_local_execution_branch_is_recovered_from_remote_before_failing():
    assert "def _switch_execution_branch" in ALTERNATING_FLOW
    assert '["git", "fetch", "origin", target_branch]' in ALTERNATING_FLOW
    assert '["git", "switch", "-C", target_branch, f"origin/{target_branch}"]' in ALTERNATING_FLOW
    assert "_switch_execution_branch(path, target_branch)" in ALTERNATING_FLOW
    assert "_switch_execution_branch(repository, target_branch)" in ALTERNATING_FLOW
