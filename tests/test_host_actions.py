import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.deploy_routes import ManualDeployConfig
from app.services.host_actions import queue_host_action


ROOT = Path(__file__).resolve().parents[1]


def test_update_local_is_written_to_pending_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVPILOT_HOST_ACTIONS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        request = queue_host_action(
            "update_local",
            transcript="atualizar local",
            actor="user:super-admin",
        )
        queued = tmp_path / request["queue_file"]
        assert queued.is_file()
        payload = json.loads(queued.read_text(encoding="utf-8"))
        assert payload["action"] == "update_local"
        assert payload["transcript"] == "atualizar local"
    finally:
        get_settings.cache_clear()


def test_manual_deploy_is_rejected_before_queue_write(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVPILOT_HOST_ACTIONS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="not allowed"):
            queue_host_action(
                "manual_deploy",
                actor="user:admin",
                project_id="project-1",
                workspace_id="workspace-1",
                project_name="DevPilot",
                command="rm -rf /tmp/should-never-run",
            )
        assert not (tmp_path / "pending").exists()
    finally:
        get_settings.cache_clear()


def test_legacy_command_field_is_not_persisted_by_manual_deploy_config():
    config = ManualDeployConfig.model_validate(
        {
            "enabled": True,
            "environment": "homolog",
            "branch": "main",
            "workdir": "devpilot",
            "timeout_seconds": 900,
            "command": "docker compose up -d --build app",
        }
    )
    assert "command" not in config.model_dump()


def test_host_runner_has_no_free_form_shell_deploy_path():
    runner = (ROOT / "tools" / "devpilot_host_action_runner.py").read_text(encoding="utf-8")
    assert 'payload.get("command")' not in runner
    assert '["bash", "-lc"' not in runner
    assert "run_manual_deploy" not in runner
    assert 'ALLOWED = {"update_local", "pipeline_repair"}' in runner


def test_deploy_admin_ui_does_not_collect_free_form_commands():
    ui = (ROOT / "app" / "static" / "deploy-admin.js").read_text(encoding="utf-8")
    assert 'name="command"' not in ui
    assert "form.elements.command" not in ui
    assert "manual_execution_available" in ui


def test_arbitrary_host_action_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVPILOT_HOST_ACTIONS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="not allowed"):
            queue_host_action("run_shell", transcript="rm anything", actor="user:test")
    finally:
        get_settings.cache_clear()
