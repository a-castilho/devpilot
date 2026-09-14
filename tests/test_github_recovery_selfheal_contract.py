from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY_RUNTIME = ROOT / "app/static/game/recovery-runtime.js"
FLOW_KEEPER = ROOT / "app/static/game/flow-keeper.js"
STABLE_UI = ROOT / "app/static/game/stable-round-ui.js"


def test_game_refresh_rechecks_legacy_github_intervention_without_user_gate():
    source = RECOVERY_RUNTIME.read_text(encoding="utf-8")

    assert "awaiting_intervention" in source
    assert "systemManagedGitHubRecovery" in source
    assert "systemManagedGitHubRecovery(recovery)" in source
    assert "safeTerminalRetry" in source


def test_flow_keeper_continues_watching_system_managed_github_recovery():
    source = FLOW_KEEPER.read_text(encoding="utf-8")

    assert "systemManagedGitHubRecovery" in source
    assert "!systemManagedGitHubRecovery(recovery)" in source
    assert "RECOVERY_RECHECK_MS" in source


def test_stable_ui_does_not_present_github_recovery_as_human_intervention():
    source = STABLE_UI.read_text(encoding="utf-8")

    assert "systemManagedGitHubRecovery" in source
    assert "Revalidando automaticamente as credenciais GitHub cadastradas" in source
    assert "!systemManagedGitHubRecovery(recovery)" in source
