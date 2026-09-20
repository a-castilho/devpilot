from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "app" / "delivery_url_recovery.py"
MANDATORY = ROOT / "app" / "mandatory_cloud_reconciler.py"
GATE = ROOT / "app" / "static" / "game" / "delivery-gate.js"
BLOCKED = ROOT / "app" / "static" / "game" / "delivery-blocked-recovery.js"
OBSERVER = ROOT / "app" / "static" / "game" / "stable-delivery-url.js"


def test_backend_owns_start_recovery_and_provider_lease():
    source = RECOVERY.read_text(encoding="utf-8")
    assert '"blocked", "failed"' in source
    assert '_RECOVERABLE_GATES = {"waiting_for_testable_url"}' in source
    assert "def _final_gate_completed(" in source
    assert 'if status == "pending":' in source
    assert "if not _final_gate_completed(db, project.id):" in source
    assert "Project.status == ProjectStatus.active" in source
    assert 'Project.repository_url != ""' in source
    assert "attempt_now = datetime.now(timezone.utc)" in source
    assert "def _try_claim_recovery(" in source
    assert "Project.codex_config == expected_config" in source
    assert "int(result.rowcount or 0) != 1" in source
    assert "recovery_last_attempt_at" in source
    assert "_BLOCKED_RECOVERY_DELAY_SECONDS = 60" in source
    assert "_FAILED_RECOVERY_DELAY_SECONDS = 90" in source
    assert 'delivery.run_delivery(db, project, "delivery-reconciler")' in source
    assert "project.delivery_recovery_completed" in source
    assert "project.delivery_recovery_retry_scheduled" in source


def test_legacy_mandatory_reconciler_delegates_to_authoritative_flow():
    source = MANDATORY.read_text(encoding="utf-8")
    run = source[source.index("def _run() -> None:"):source.index("def start() -> None:")]
    assert "from app.delivery_url_recovery import _reconcile_once" in run
    assert "processed = _reconcile_once()" in run
    assert "delivery.run_delivery" not in run


def test_browser_auto_flow_is_observer_only_and_manual_retry_is_explicit():
    gate = GATE.read_text(encoding="utf-8")
    blocked = BLOCKED.read_text(encoding="utf-8")
    observer = OBSERVER.read_text(encoding="utf-8")

    assert "/delivery/auto" not in gate
    assert "scheduleDeliveryRetry" not in gate
    assert "DELIVERY_RETRY_MS" not in gate
    assert "finalVerifierApproved" in gate
    assert "backend detects Gate 7/7" in gate

    assert "method: 'POST'" not in blocked
    assert "/retry" not in blocked

    assert "WATCH_MS = 15000" in observer
    assert "const call = async path" in observer
    assert "${endpoint(projectId)}/retry" in observer
    assert "data-stable-delivery-retry" in observer
    assert "method: 'POST'" in observer
