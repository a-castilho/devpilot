from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import TaskStatus
from app.task_documentation_routes import build_task_documentation, router


def test_build_task_documentation_uses_real_task_and_run_evidence():
    task = SimpleNamespace(
        id="task-12345678",
        title="Implementar botão Próximo",
        status=TaskStatus.completed,
        source="dashboard",
        branch_name="feat/next-button",
        prompt="Implementar avanço seguro e auditável.",
    )
    project = SimpleNamespace(name="DevPilot")
    now = datetime.now(timezone.utc)
    run = SimpleNamespace(
        id="run-1",
        attempt=1,
        status="success",
        summary="Testes concluídos com sucesso.",
        logs='{"summary":"Implementação validada."}',
        commit_sha="abc123",
        pull_request_url="https://github.com/example/repo/pull/1",
        started_at=now,
        finished_at=now,
    )

    markdown = build_task_documentation(task, project, [run])

    assert "Implementar botão Próximo" in markdown
    assert "Implementar avanço seguro e auditável." in markdown
    assert "Implementação validada." in markdown
    assert "Testes concluídos com sucesso." in markdown
    assert "abc123" in markdown
    assert "1 execução(ões) bem-sucedida(s)" in markdown
    assert "Aprendizado para o usuário" in markdown


def test_documentation_route_exists_as_post():
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", "") == "/api/tasks/{task_id}/documentation"
    ]

    assert len(matches) == 1
    assert "POST" in matches[0].methods


def test_frontend_bundle_contains_completed_task_documentation_action():
    source = open("app/static/task-completion-documentation.js", encoding="utf-8").read()
    loader = open("app/static/feature-loader.js", encoding="utf-8").read()

    assert "Gerar documentação" in source
    assert "statusValue !== 'completed'" in source
    assert "/documentation" in source
    assert "task-completion-documentation.js" in loader


def test_queued_tasks_only_add_archive_as_orchestrator_action():
    source = open("app/static/task-completion-documentation.js", encoding="utf-8").read()

    queued_block = source.split("else if (statusValue === 'queued') {", 1)[1].split(
        "} else if (['paused', 'pause_requested'].includes(statusValue)) {", 1
    )[0]

    assert "actionButton('Arquivar', 'archive'" in queued_block
    assert "actionButton('Próximo', 'next'" not in queued_block
    assert "actionButton('Continuar automaticamente', 'auto'" not in queued_block
    assert "actionButton('Retomar', 'resume'" not in queued_block


def test_paused_tasks_keep_resume_and_archive_only():
    source = open("app/static/task-completion-documentation.js", encoding="utf-8").read()

    paused_block = source.split("else if (['paused', 'pause_requested'].includes(statusValue)) {", 1)[1].split(
        "} else if (statusValue !== 'completed') {", 1
    )[0]

    assert "actionButton('Retomar', 'resume'" in paused_block
    assert "actionButton('Arquivar', 'archive'" in paused_block
    assert "actionButton('Próximo', 'next'" not in paused_block
    assert "actionButton('Continuar automaticamente', 'auto'" not in paused_block
