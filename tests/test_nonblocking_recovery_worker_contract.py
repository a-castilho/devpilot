from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / "app/worker.py").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/services/recovery.py").read_text(encoding="utf-8")
FAILURE_RECOVERY = (ROOT / "app/services/failure_recovery.py").read_text(encoding="utf-8")


def test_worker_turns_exhausted_safe_failure_into_degraded_continuation():
    assert "recovery.should_continue_pipeline(decision)" in WORKER
    assert "recovery.degraded_result(" in WORKER
    assert '"deferred"' in WORKER
    assert 'result.get("degraded")' in WORKER
    assert 'run.status = "success" if result.get("exit_code", 0) == 0 else "failed"' in WORKER
    assert '"pipeline_continued"' in WORKER


def test_worker_creates_background_ai_repair_instead_of_blocking_pipeline():
    assert "ensure_deferred_failure_recovery_task" in WORKER
    assert "generated_deferred_recovery" in WORKER
    assert 'actor="worker"' in WORKER
    assert '"generated_deferred_recovery_task_id"' in WORKER
    assert "failure_recovery.deferred_created" in FAILURE_RECOVERY


def test_worker_keeps_real_hard_stop_as_failure_path():
    assert 'getattr(decision, "hard_stop", False)' in WORKER
    assert "failure_result(decision" in WORKER
    assert '"hard_stop"' in RECOVERY
    assert '"protect_integrity"' in RECOVERY


def test_contextual_report_says_degraded_pipeline_continues_without_claiming_delivery():
    assert "continuação degradada" in WORKER.lower()
    assert "a esteira continuará" in WORKER.lower()
    assert "não representa entrega técnica concluída" in WORKER.lower()


def test_degraded_recovery_task_does_not_recursively_spawn_another_recovery():
    assert "if is_failure_recovery_task(original_task):" in FAILURE_RECOVERY
    assert "if is_failure_recovery_task(task):" in WORKER
