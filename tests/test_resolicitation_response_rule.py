import json

from app.models import Run, Task
from app.task_run_routes import _resolicitation_prompt, _run_response, router


def _task() -> Task:
    return Task(
        id="task-original",
        workspace_id="workspace-1",
        project_id="project-1",
        title="Análise técnica do projeto",
        prompt="Analise o projeto e apresente os problemas encontrados.",
        source="dashboard",
        priority=70,
    )


def _run(*, logs: dict | None = None, summary: str = "") -> Run:
    return Run(
        id="run-original",
        task_id="task-original",
        attempt=1,
        status="success",
        summary=summary,
        logs=json.dumps(logs or {}, ensure_ascii=False),
    )


def test_resolicitation_prefers_previous_client_response():
    run = _run(
        logs={
            "client_report": "Resposta anterior real do agente com o diagnóstico.",
            "stdout": "saída técnica que não deve ter prioridade",
        },
        summary="resumo curto",
    )

    assert _run_response(run) == "Resposta anterior real do agente com o diagnóstico."


def test_resolicitation_falls_back_to_run_summary_when_logs_have_no_response():
    run = _run(logs={"result": {}}, summary="Resposta registrada no resumo da execução.")

    assert _run_response(run) == "Resposta registrada no resumo da execução."


def test_resolicitation_prompt_makes_previous_response_the_correction_base():
    task = _task()
    run = _run(summary="Análise anterior")

    prompt = _resolicitation_prompt(
        task,
        run,
        "A tela atual tem todos os cards com a mesma resposta.",
        "Corrija para que cada item tenha uma resposta coerente com o próprio contexto.",
    )

    assert "[DEVPILOT_RESOLICITATION_V1]" in prompt
    assert "[resolicitation-origin-task:task-original]" in prompt
    assert "[resolicitation-origin-run:run-original]" in prompt
    assert "Não comece a resposta do zero" in prompt
    assert "RESPOSTA ANTERIOR A SER CORRIGIDA" in prompt
    assert "A tela atual tem todos os cards com a mesma resposta." in prompt
    assert "NOVA ORIENTAÇÃO DE CORREÇÃO" in prompt
    assert "Corrija para que cada item tenha uma resposta coerente" in prompt


def test_resolicitation_route_is_registered_as_system_flow():
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", "") == "/api/tasks/{task_id}/resolicit"
        and "POST" in getattr(route, "methods", set())
    ]

    assert len(matches) == 1
