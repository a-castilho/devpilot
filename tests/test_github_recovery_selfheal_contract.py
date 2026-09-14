import json
from pathlib import Path
from types import SimpleNamespace

from app.task_run_routes import failure_details


ROOT = Path(__file__).resolve().parents[1]
RECOVERY_RUNTIME = ROOT / "app/static/game/recovery-runtime.js"


def test_github_failure_is_system_managed_not_user_authorization():
    run = SimpleNamespace(
        status="failed",
        summary="Execution failed",
        logs=json.dumps({"stderr": "fatal: repository access denied"}),
    )

    details = failure_details(run)

    assert details["category"] == "github_auth"
    assert details["requires_authorization"] is False


def test_legacy_github_self_healing_authorization_flag_is_normalized():
    run = SimpleNamespace(
        status="failed",
        summary="Execution failed",
        logs=json.dumps(
            {
                "stderr": "The requested URL returned error: 403",
                "self_healing": {
                    "category": "github_auth",
                    "message": "Legacy recovery record",
                    "requires_authorization": True,
                },
            }
        ),
    )

    details = failure_details(run)

    assert details["category"] == "github_auth"
    assert details["requires_authorization"] is False


def test_game_refresh_rechecks_legacy_github_intervention_without_user_gate():
    source = RECOVERY_RUNTIME.read_text(encoding="utf-8")

    assert "awaiting_intervention" in source
    assert "systemManagedGitHubRecovery" in source
    assert "systemManagedGitHubRecovery(recovery)" in source
