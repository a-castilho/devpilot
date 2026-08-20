import json

import pytest

from app.config import get_settings
from app.services.host_actions import queue_host_action


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


def test_arbitrary_host_action_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVPILOT_HOST_ACTIONS_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="not allowed"):
            queue_host_action("run_shell", transcript="rm anything", actor="user:test")
    finally:
        get_settings.cache_clear()
