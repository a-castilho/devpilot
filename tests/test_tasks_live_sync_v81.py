from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "app/static/tasks-operational-ui.js").read_text(encoding="utf-8")


def test_executions_refresh_real_state_while_screen_is_open():
    assert "window.__devpilotTasksLiveSyncV81 = true" in UI
    assert "const LIVE_POLL_MS = 3000" in UI
    assert "function tasksViewIsVisible()" in UI
    assert "function syncLiveTasks()" in UI
    assert "taskSignature(rows)" in UI
    assert "nextSignature !== ui.liveSignature" in UI
    assert "state.tasks = rows" in UI
    assert "renderOperationalTasks()" in UI
    assert "MutationObserver" not in UI


def test_live_sync_uses_same_compact_execution_source_as_manual_refresh():
    assert UI.count("/ui/tasks?limit=${safeLimit}") >= 2
    assert "{retry:false, timeoutMs:5000}" in UI
    assert "ui.detailCache.clear()" in UI
