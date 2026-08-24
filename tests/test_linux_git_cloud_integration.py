import time
from pathlib import Path

from app.linux_agent.runtime import SessionManager


ROOT = Path(__file__).resolve().parents[1]


def _wait_for(manager: SessionManager, session_id: str, needle: str) -> str:
    deadline = time.time() + 3
    output = ""
    sequence = 0
    while time.time() < deadline and needle not in output:
        data = manager.output(session_id, after=sequence)
        sequence = data["last_sequence"]
        output += "".join(chunk["text"] for chunk in data["chunks"])
        time.sleep(0.05)
    return output


def test_github_cloud_auth_is_injected_without_persisting_token(tmp_path):
    manager = SessionManager(tmp_path, shell="/bin/sh")
    token = "github-test-token-123456789"
    session = manager.create(
        actor="user:test",
        cwd=str(tmp_path),
        git_auth={"provider": "github", "host": "github.com", "token": token},
    )
    try:
        assert session["git_provider"] == "github"
        manager.send_input(
            session["id"],
            "printf 'git=%s token=%s config=%s\\n' \"$DEVPILOT_GIT_PROVIDER\" \"${GH_TOKEN:+set}\" \"$GIT_CONFIG_COUNT\"\n",
        )
        output = _wait_for(manager, session["id"], "git=github token=set config=2")
        assert "git=github token=set config=2" in output

        metadata = (tmp_path / "sessions" / session["id"] / "session.json").read_text(encoding="utf-8")
        assert token not in metadata
    finally:
        manager.close(session["id"])


def test_linux_route_wires_cloud_github_only_for_super_admin():
    source = (ROOT / "app/linux_routes.py").read_text(encoding="utf-8")

    assert '_GITHUB_CLOUD_PROVIDER = "cloud:github"' in source
    assert "if principal.role is not Role.SUPER_ADMIN:" in source
    assert 'request_payload["git_auth"] = git_auth' in source
    assert '"git_cloud_integrated": bool(git_auth)' in source


def test_linux_agent_accepts_only_github_com_cloud_auth():
    source = (ROOT / "app/linux_agent/main.py").read_text(encoding="utf-8")

    assert 'provider: Literal["github"]' in source
    assert 'host: Literal["github.com"]' in source
    assert "git_auth=payload.git_auth.model_dump() if payload.git_auth else None" in source


def test_dedicated_linux_user_can_receive_only_preserved_git_environment():
    runtime = (ROOT / "app/linux_agent/runtime.py").read_text(encoding="utf-8")
    installer = (ROOT / "scripts/install-linux-agent.sh").read_text(encoding="utf-8")

    assert 'command.append(f"--preserve-env={' in runtime
    assert '"GH_TOKEN": token' in runtime
    assert '"credential.https://github.com.helper"' in runtime
    assert "NOPASSWD:SETENV:" in installer
