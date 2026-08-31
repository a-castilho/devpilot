from __future__ import annotations

import subprocess
from pathlib import Path

from app.services import runner_status as runner_status_module


ROOT = Path(__file__).resolve().parents[1]


def _completed(*, code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["systemctl"], code, stdout=stdout, stderr=stderr)


def test_runner_status_reports_supervised_online(monkeypatch):
    monkeypatch.setattr(runner_status_module.shutil, "which", lambda _name: "/usr/bin/systemctl")

    def fake_run(command, **_kwargs):
        if "is-active" in command:
            return _completed(code=0, stdout="active\n")
        return _completed(code=0, stdout="enabled\n")

    monkeypatch.setattr(runner_status_module.subprocess, "run", fake_run)

    status = runner_status_module.runner_status()

    assert status["status"] == "online"
    assert status["online"] is True
    assert status["service_enabled"] is True
    assert status["label"] == "devpilot-ci"
    assert status["scope"] == "github_actions"


def test_runner_status_reports_offline_without_exposing_process_details(monkeypatch):
    monkeypatch.setattr(runner_status_module.shutil, "which", lambda _name: "/usr/bin/systemctl")
    monkeypatch.setattr(
        runner_status_module.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(code=3, stdout="inactive\n"),
    )

    status = runner_status_module.runner_status()

    assert status["status"] == "offline"
    assert status["online"] is False
    assert "CI pode permanecer aguardando runner" in str(status["detail"])
    assert "token" not in str(status).lower()


def test_runner_status_unknown_does_not_claim_task_worker_is_down(monkeypatch):
    monkeypatch.setattr(runner_status_module.shutil, "which", lambda _name: None)

    status = runner_status_module.runner_status()

    assert status["status"] == "unknown"
    assert status["scope"] == "github_actions"
    assert "GitHub Actions Runner" in str(status["detail"])
    assert "não representa o estado do worker de tarefas" in str(status["detail"])


def test_runner_setup_is_systemd_supervised_and_has_no_nohup():
    source = (ROOT / "scripts/setup-github-self-hosted-runner.sh").read_text()

    assert "Restart=always" in source
    assert 'systemctl --user enable --now "$SERVICE_NAME"' in source
    assert "loginctl enable-linger" in source
    assert "nohup" not in source


def test_super_admin_system_map_surfaces_runner_outage():
    source = (ROOT / "app/static/super-admin-system-map.js").read_text()
    routes = (ROOT / "app/host_action_routes.py").read_text()

    assert "/api/voice/runner-status" in source
    assert "CI e PRs podem permanecer aguardando" in source
    assert '@router.get("/runner-status")' in routes
    assert "Depends(require_super_admin)" in routes
