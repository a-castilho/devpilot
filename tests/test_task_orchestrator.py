from app.task_documentation_routes import _command_action, router


def _route(path: str, method: str):
    return [
        item
        for item in router.routes
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set())
    ]


def test_orchestrator_routes_share_the_existing_authenticated_task_router():
    for action in ("next", "auto", "pause", "resume", "cancel", "archive"):
        assert len(_route(f"/api/tasks/{{task_id}}/{action}", "POST")) == 1
    assert len(_route("/api/tasks/{task_id}/orchestrator", "GET")) == 1
    assert len(_route("/api/tasks/orchestrator/runtime", "GET")) == 1
    assert len(_route("/api/tasks/{task_id}/command", "POST")) == 1


def test_ui_chat_and_voice_commands_resolve_to_the_same_orchestrator_actions():
    assert _command_action("Próximo") == "next"
    assert _command_action("continuar automaticamente") == "auto_advance"
    assert _command_action("parar") == "pause"
    assert _command_action("retomar") == "resume"
    assert _command_action("cancelar") == "cancel"
    assert _command_action("excluir") == "archive"


def test_worker_uses_atomic_claim_and_real_process_control():
    source = open("app/worker.py", encoding="utf-8").read()
    orchestrator = open("app/services/task_orchestrator.py", encoding="utf-8").read()

    assert "claim_next_task" in source
    assert ".returning(Task.id)" not in orchestrator
    assert "candidate_id = db.scalar(" in orchestrator
    assert "Task.id == candidate_id" in orchestrator
    assert "Task.status == TaskStatus.queued" in orchestrator
    assert "int(result.rowcount or 0) != 1" in orchestrator
    assert "start_new_session=True" in orchestrator
    assert "os.killpg" in orchestrator
    assert "pause_requested" in orchestrator
    assert "cancel_requested" in orchestrator


def test_orchestrator_preserves_gates_learning_archive_and_idempotent_game_reward():
    source = open("app/services/task_orchestrator.py", encoding="utf-8").read()

    assert "evaluate_task" in source
    assert "awaiting_approval" in source
    assert "task_learning_events" in source
    assert "Arquivamento lógico" in source
    assert "QuestMissionStatus.completed.value" in source
    assert "QUEST_REWARD_GRANTED" in source
    assert "rbac_unchanged" in source


def test_task_bundle_exposes_contextual_controls_without_eager_boot_change():
    source = open("app/static/task-completion-documentation.js", encoding="utf-8").read()
    loader = open("app/static/feature-loader.js", encoding="utf-8").read()

    for label in ("Próximo", "Continuar automaticamente", "Parar", "Retomar", "Cancelar", "Arquivar"):
        assert label in source
    for learning_field in ("O que aconteceu", "Por que", "Conceito", "Observe", "Aprendizado"):
        assert learning_field in source
    assert "/tasks/orchestrator/runtime" in source
    assert "runtime?.state === 'archived'" in source
    assert "task-completion-documentation.js" in loader
    assert "task-completion-documentation.js" in loader.split("tasks:", 1)[1].split("],", 1)[0]
