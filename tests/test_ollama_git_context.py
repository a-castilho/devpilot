from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.services import ollama_git_context, ollama_voice_bridge


def test_repository_url_is_recovered_from_selected_project_context():
    input_text = (
        "Projeto selecionado: DevPilot. Descrição: automação. "
        "Repositório: https://github.com/a-castilho/devpilot.git. Branch padrão: main.\n\n"
        "CLIENTE: leia o Git\nDEVPILOT:"
    )

    assert (
        ollama_git_context.repository_url_from_input(input_text)
        == "https://github.com/a-castilho/devpilot.git"
    )


def test_git_context_reads_remote_ref_and_relevant_files(monkeypatch):
    project = SimpleNamespace(
        repository_url="https://github.com/a-castilho/devpilot.git",
        default_branch="main",
    )
    repository = Path("/tmp/devpilot-test-repository")
    monkeypatch.setattr(ollama_git_context, "ensure_repository", lambda _: repository)

    def fake_run(args, cwd=None, timeout=20):
        command = " ".join(args)
        if "ls-tree" in args:
            stdout = "AGENTS.md\nREADME.md\napp/services/ollama_voice_bridge.py\napp/api.py\n"
        elif "grep" in args:
            stdout = "origin/main:app/services/ollama_voice_bridge.py\n"
        elif "status" in args:
            stdout = "## main...origin/main\n"
        elif "log" in args:
            stdout = "abc1234 2026-08-24 feat: improve Ollama\n"
        elif "show" in args and "AGENTS.md" in command:
            stdout = "# AGENTS\nUse o projeto selecionado.\n"
        elif "show" in args and "ollama_voice_bridge.py" in command:
            stdout = "def try_registered_ollama():\n    pass\n"
        elif "show" in args and "README.md" in command:
            stdout = "# DevPilot\n"
        else:
            stdout = ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(ollama_git_context, "run", fake_run)

    context = ollama_git_context._build_context_for_project(
        project,
        "\nCLIENTE: revisar ollama voice bridge\nDEVPILOT:",
    )

    assert "CONTEXTO GIT SOMENTE LEITURA" in context
    assert "Ref lida: origin/main" in context
    assert "abc1234" in context
    assert "ARQUIVO app/services/ollama_voice_bridge.py" in context


def test_ollama_bridge_injects_selected_project_git_context(monkeypatch):
    monkeypatch.setattr(ollama_voice_bridge, "_registered_models", lambda: ["tinyllama"])
    monkeypatch.setattr(
        ollama_voice_bridge,
        "build_ollama_git_context",
        lambda _: "CONTEXTO GIT SOMENTE LEITURA\nARQUIVO app/api.py\nconteudo real",
    )

    calls = []

    class FakeAgent:
        timeout = 0

        def request(self, method, path, payload=None):
            calls.append((method, path, payload or {}))
            if path == "/v1/ollama/ensure":
                return {"models": ["tinyllama"]}
            if path == "/v1/ollama/chat":
                return {
                    "answer": "Li o Git do projeto selecionado.",
                    "input_tokens": 20,
                    "output_tokens": 8,
                }
            raise AssertionError(path)

    monkeypatch.setattr(ollama_voice_bridge, "LinuxAgentClient", FakeAgent)

    result, attempts = asyncio.run(
        ollama_voice_bridge.try_registered_ollama(
            None,
            "Projeto selecionado: DevPilot. Repositório: https://github.com/a-castilho/devpilot.git. Branch padrão: main.",
            "Responda em português.",
        )
    )

    assert attempts == []
    assert result is not None
    assert result["provider"] == "ollama"
    chat_payload = next(payload for _, path, payload in calls if path == "/v1/ollama/chat")
    assert "CONTEXTO GIT SOMENTE LEITURA" in chat_payload["input_text"]
    assert "app/api.py" in chat_payload["input_text"]
    assert "fatos lidos do Git" in chat_payload["instructions"]
