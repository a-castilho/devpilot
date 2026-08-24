from pathlib import Path


LINUX_UI = Path("app/static/linux-terminal.js")


def test_linux_workspace_has_beginner_guided_actions():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert "Você não precisa saber comandos para começar." in source
    assert 'data-linux-command="pwd"' in source
    assert 'data-linux-command="ls -lah"' in source
    assert 'data-linux-command="free -h"' in source
    assert 'data-linux-command="df -h"' in source
    assert "Estas ações são somente de consulta" in source


def test_linux_workspace_integrates_voice_assistance():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert 'id="linux-voice-help"' in source
    assert "openVoiceHelp" in source
    assert "Assistente Linux: fale normalmente" in source
    assert 'id="linux-explain-output"' in source
    assert "Explique esta saída em português simples" in source


def test_linux_terminal_cleans_ansi_noise_for_beginner_readability():
    source = LINUX_UI.read_text(encoding="utf-8")

    assert "stripAnsi" in source
    assert "output.textContent += clean" in source
