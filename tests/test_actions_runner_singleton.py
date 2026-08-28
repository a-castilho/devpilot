from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup-github-self-hosted-runner.sh"


def test_runner_setup_refuses_duplicate_online_session():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "remote_runner_json" in text
    assert 'if [[ "$remote_status" == "online" ]]' in text
    assert "não iniciarei uma segunda sessão" in text
    assert "SessionConflictException" in text


def test_runner_setup_recovers_existing_listener_without_pid_file():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'listener="$RUNNER_DIR/bin/Runner.Listener"' in text
    assert 'printf \'%s\\n\' "$listener_pid" >"$PID_FILE"' in text
    assert "aguardando reconexão em vez de duplicar sessão" in text
