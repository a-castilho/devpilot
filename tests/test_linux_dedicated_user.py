from pathlib import Path

import pytest

from app.linux_agent.runtime import SessionManager, TerminalUserUnavailable


ROOT = Path(__file__).resolve().parents[1]


def test_direct_terminal_fails_closed_when_dedicated_user_is_missing(tmp_path):
    manager = SessionManager(
        tmp_path,
        shell="/bin/sh",
        direct_user="devpilot-user-that-must-not-exist-93841",
    )

    status = manager.direct_user_status()

    assert status["configured"] is True
    assert status["ready"] is False
    assert status["reason"] == "Usuário Linux dedicado ainda não existe"
    with pytest.raises(TerminalUserUnavailable):
        manager.create(actor="user:test", use_direct_user=True)


def test_normal_isolated_workspace_session_keeps_existing_runtime_behavior(tmp_path):
    manager = SessionManager(
        tmp_path,
        shell="/bin/sh",
        direct_user="devpilot-user-that-must-not-exist-93841",
    )
    session = manager.create(actor="user:test", cwd=str(tmp_path), use_direct_user=False)
    try:
        assert session["linux_user"]
        assert session["cwd"] == str(tmp_path.resolve())
    finally:
        manager.close(session["id"])


def test_install_script_provisions_locked_dedicated_account_and_narrow_launcher():
    source = (ROOT / "scripts" / "install-linux-agent.sh").read_text(encoding="utf-8")

    assert 'TERMINAL_USER="${DEVPILOT_LINUX_TERMINAL_USER:-devpilot}"' in source
    assert "sudo useradd" in source
    assert 'sudo passwd -l "${TERMINAL_USER}"' in source
    assert "DEVPILOT_LINUX_TERMINAL_USER=${TERMINAL_USER}" in source
    assert "DEVPILOT_LINUX_TERMINAL_LAUNCHER=${TERMINAL_LAUNCHER}" in source
    assert "NOPASSWD:SETENV: %s" in source
    assert "/usr/local/libexec/devpilot-terminal-shell" in source
    assert "sudo usermod -aG sudo" not in source
    assert "sudo usermod -aG docker" not in source


def test_direct_api_never_accepts_or_falls_back_to_interactive_os_user():
    agent_source = (ROOT / "app" / "linux_agent" / "main.py").read_text(encoding="utf-8")
    routes_source = (ROOT / "app" / "linux_routes.py").read_text(encoding="utf-8")

    assert "use_direct_user=not isolated_workspace" in agent_source
    assert '"mode": "dedicated-linux-user" if super_admin else "isolated-user-workspace"' in routes_source
    assert '"linux_user": session.get("linux_user")' in routes_source


def test_linux_ui_shows_the_real_dedicated_account():
    source = (ROOT / "app" / "static" / "linux-terminal.js").read_text(encoding="utf-8")

    assert "Conta Linux isolada:" in source
    assert "session.linux_user" in source
    assert "aberto · ${session.linux_user}" in source
