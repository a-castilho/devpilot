from app.services.recovery import AutoRecoveryService
from app.worker import PIPELINE_BLOCKING_STATUSES


def test_unknown_failure_is_terminal_for_current_pipeline_run():
    decision = AutoRecoveryService().recover(None, None, "unexpected execution failure", 1)

    assert decision.status == "needs_attention"
    assert decision.retry is False
    assert decision.status in PIPELINE_BLOCKING_STATUSES


def test_filesystem_permission_does_not_enter_automatic_retry_loop():
    decision = AutoRecoveryService().recover(None, None, "read-only file system", 1)

    assert decision.status == "needs_authorization"
    assert decision.retry is False
    assert decision.status in PIPELINE_BLOCKING_STATUSES


def test_network_failure_remains_bounded_and_retryable(monkeypatch):
    monkeypatch.setattr("app.services.recovery.time.sleep", lambda _: None)
    decision = AutoRecoveryService().recover(None, None, "Could not resolve host: github.com", 1)

    assert decision.status == "retrying"
    assert decision.retry is True
    assert decision.status not in PIPELINE_BLOCKING_STATUSES
