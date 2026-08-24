from pathlib import Path


LINUX_UI = Path("app/static/linux-terminal.js")


def test_linux_workspace_has_simple_guided_actions():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert "Meu Linux" in source
    assert 'data-linux-command="pwd"' in source
    assert 'data-linux-command="ls -lah"' in source
    assert 'data-linux-command="free -h"' in source
    assert 'data-linux-command="df -h /"' in source
    assert "Escolha uma ação acima ou abra o terminal" in source


def test_linux_terminal_polls_output_even_when_embedded_in_dashboard():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert "async function pollOutput()" in source
    assert "if (!sessionId) return;" in source
    assert "if (!visible || !sessionId) return;" not in source
    assert "startPolling();" in source
    assert "window.setTimeout(pollOutput, 60);" in source


def test_linux_terminal_cleans_ansi_noise_for_readability():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert "cleanOutput" in source
    assert "output.textContent += clean" in source
    assert "DEVPILOT_CAPTURE_" in source
