from pathlib import Path


LINUX_UI = Path("app/static/linux-terminal.js")
LINUX_UPDATE_UI = Path("app/static/linux-update-command.js")
LINUX_COACH_UI = Path("app/static/linux-beginner-coach.js")
VERCEL_BUILD = Path("tools/build-vercel-static.mjs")


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


def test_linux_screen_has_super_admin_update_command():
    source = LINUX_UPDATE_UI.read_text(encoding="utf-8")
    coach = LINUX_COACH_UI.read_text(encoding="utf-8")
    build = VERCEL_BUILD.read_text(encoding="utf-8")

    assert "linux-update-local" in source
    assert "button.textContent = 'Atualizar'" in source
    assert "status?.profile?.role === 'SUPER_ADMIN'" in source
    assert "'/api/voice/system-actions'" in source
    assert "JSON.stringify({transcript: 'atualizar local'})" in source
    assert "/assets/linux-update-command.js?v=20260824-1" in coach
    assert "'linux-update-command.js'" in build
