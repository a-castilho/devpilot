import json
from pathlib import Path

from app.models import Run, Task, TaskStatus
from app.task_run_routes import failure_details, result_contract


ROOT = Path(__file__).resolve().parents[1]


def task(*, title="Implementar login", source="dashboard", prompt="", status=TaskStatus.failed):
    return Task(
        workspace_id="workspace-1",
        project_id="project-1",
        title=title,
        prompt=prompt,
        source=source,
        status=status,
        priority=80,
    )


def run(*, status="failed", summary="falhou", logs=None):
    return Run(
        task_id="task-1",
        status=status,
        summary=summary,
        logs=json.dumps(logs or {}, ensure_ascii=False),
    )


def test_resolved_self_healing_is_not_reported_as_successful_execution():
    item = run(
        logs={
            "exit_code": 1,
            "summary": "Atenção necessária: a credencial GitHub foi validada novamente e o acesso está disponível.",
            "self_healing": {
                "status": "resolved",
                "category": "github_auth",
                "message": "A credencial GitHub foi validada novamente e o acesso está disponível.",
                "requires_authorization": False,
                "steps": [
                    {"state": "resolved", "message": "Credencial atual validada; a tarefa será repetida automaticamente."}
                ],
            },
        }
    )

    failure = failure_details(item)
    contract = result_contract(task(), item)

    assert failure["category"] == "retest_required"
    assert failure["code"] == "RECOVERY_RETEST_REQUIRED"
    assert "execução" in failure["message"].lower()
    assert "comprovar" in failure["message"].lower()
    assert contract["state"] == "retest_required"
    assert contract["headline"] == "Correção aplicada · reteste pendente"
    assert "não trate" in contract["next_action"].lower()


def test_result_contract_separates_analysis_execution_verification_and_recovery():
    analysis = task(
        title="Análise técnica de DevPilot",
        source="analysis",
        prompt="[DEVPILOT_MODE=analysis-read-only]\nNão modifique arquivos.",
        status=TaskStatus.completed,
    )
    execution = task(
        title="Ação recomendada · DevPilot",
        source="analysis-action",
        prompt="[DEVPILOT_STAGE=execute]\n[DEVPILOT_MODE=fix]\n[analysis-action]",
        status=TaskStatus.completed,
    )
    verification = task(
        title="Validação pós-execução · DevPilot",
        source="execution-verification",
        prompt="[DEVPILOT_STAGE=verify]\n[DEVPILOT_MODE=analysis-read-only]\n[post-execution-verification]",
        status=TaskStatus.completed,
    )
    recovery = task(
        title="Recuperação · Análise técnica de DevPilot",
        source="failure-recovery",
        prompt="[DEVPILOT_FAILURE_RECOVERY_V1]\n[DEVPILOT_MODE=fix]",
        status=TaskStatus.completed,
    )
    ok = run(status="success", summary="ok", logs={"exit_code": 0, "summary": "ok"})

    assert result_contract(analysis, ok)["kind"] == "analysis"
    assert result_contract(execution, ok)["kind"] == "execution"
    assert result_contract(verification, ok)["kind"] == "verification"
    assert result_contract(recovery, ok)["kind"] == "recovery"


def test_execution_product_ui_uses_product_contract_and_hides_raw_output_by_default():
    source = (ROOT / "app/static/execution-results-v28.js").read_text(encoding="utf-8")

    assert "PRODUTO DA MISSÃO" in source
    assert "Correção aplicada · reteste pendente" in source
    assert "PRÓXIMO PASSO" in source
    assert "EVIDÊNCIAS" in source
    assert "Saída técnica (auditoria)" in source
    assert '<details class="dp-v28-output">' in source
    assert '<details class="dp-v28-output" open>' not in source
    assert "Não use esta seção isoladamente como estado final do produto." in source


def test_tasks_operational_ui_does_not_treat_analysis_action_as_analysis():
    source = (ROOT / "app/static/tasks-operational-ui.js").read_text(encoding="utf-8")

    assert "source === 'analysis-action'" in source
    assert "return 'execution'" in source
    assert "source === 'execution-verification'" in source
    assert "return 'verification'" in source
    assert "source === 'failure-recovery'" in source
    assert "return 'recovery'" in source
    assert "<option value=\"verification\">Validação</option>" in source
    assert "<option value=\"recovery\">Recuperação</option>" in source
    assert "Tipo de missão" in source
