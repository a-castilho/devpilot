import time

from app.linux_agent.runtime import SessionManager


def _read_until(manager, session_id: str, marker: str, timeout: float = 3.0) -> str:
    deadline = time.time() + timeout
    output = ""
    sequence = 0
    while time.time() < deadline and marker not in output:
        data = manager.output(session_id, after=sequence)
        sequence = data["last_sequence"]
        output += "".join(chunk["text"] for chunk in data["chunks"])
        time.sleep(0.05)
    return output


def test_persistent_terminal_session(tmp_path):
    manager = SessionManager(tmp_path, shell="/bin/sh")
    session = manager.create(actor="user:test", cwd=str(tmp_path))
    try:
        manager.send_input(session["id"], "cd /\nprintf 'devpilot-linux-agent-ok\\n'\n")
        output = _read_until(manager, session["id"], "devpilot-linux-agent-ok")
        assert "devpilot-linux-agent-ok" in output
    finally:
        closed = manager.close(session["id"])
        assert closed["state"] == "closed"


def test_isolated_terminal_home_resolves_to_workspace(tmp_path, monkeypatch):
    host_home = tmp_path / "host-home"
    workspace = tmp_path / "isolated-workspace"
    host_home.mkdir()
    workspace.mkdir()
    (host_home / "HOST_ONLY").write_text("secret", encoding="utf-8")
    (workspace / "Documents").mkdir()
    monkeypatch.setenv("HOME", str(host_home))

    manager = SessionManager(tmp_path / "agent-data", shell="/bin/sh")
    session = manager.create(
        actor="user:tenant-a",
        cwd=str(workspace),
        isolated_home=True,
    )
    try:
        manager.send_input(
            session["id"],
            "printf 'HOME=%s\\n' \"$HOME\"\n"
            "cd ~/Documents\n"
            "printf 'PWD=%s\\n' \"$PWD\"\n"
            "test ! -e ~/HOST_ONLY && printf 'isolated-home-ok\\n'\n",
        )
        output = _read_until(manager, session["id"], "isolated-home-ok")
        assert f"HOME={workspace}" in output
        assert f"PWD={workspace / 'Documents'}" in output
        assert "isolated-home-ok" in output
        assert str(host_home) not in output
    finally:
        manager.close(session["id"])
