import time

from app.linux_agent.runtime import SessionManager


def test_persistent_terminal_session(tmp_path):
    manager = SessionManager(tmp_path, shell="/bin/sh")
    session = manager.create(actor="user:test", cwd=str(tmp_path))
    try:
        manager.send_input(session["id"], "cd /\nprintf 'devpilot-linux-agent-ok\\n'\n")
        deadline = time.time() + 3
        output = ""
        sequence = 0
        while time.time() < deadline and "devpilot-linux-agent-ok" not in output:
            data = manager.output(session["id"], after=sequence)
            sequence = data["last_sequence"]
            output += "".join(chunk["text"] for chunk in data["chunks"])
            time.sleep(0.05)
        assert "devpilot-linux-agent-ok" in output
    finally:
        closed = manager.close(session["id"])
        assert closed["state"] == "closed"
