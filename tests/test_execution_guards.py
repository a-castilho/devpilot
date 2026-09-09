from types import SimpleNamespace

from app.services.execution_guards import (
    _add_workspace_write,
    _combine_failure_streams,
    _enforce_required_evidence,
    _is_read_only_prompt,
)


def test_workspace_write_is_added_to_development_codex_command():
    command = _add_workspace_write(["codex", "exec", "--json", "prompt"])

    assert command[:4] == ["codex", "exec", "--sandbox", "workspace-write"]
    assert command.count("--sandbox") == 1


def test_read_only_analysis_remains_read_only():
    assert _is_read_only_prompt("[DEVPILOT_MODE=analysis-read-only]\nAnalise o projeto")
    assert _is_read_only_prompt("This is a READ-ONLY ANALYSIS. Inspect the repository")
    assert not _is_read_only_prompt("[DEVPILOT_BUILD_GAME_V1]\nCrie o plano")


def test_build_game_success_is_rejected_without_required_evidence(tmp_path):
    executor = SimpleNamespace(repository_path=lambda _project: tmp_path)
    project = SimpleNamespace()
    task = SimpleNamespace(
        title="[Jogo] Etapa 1 · Planejamento",
        prompt="[DEVPILOT_BUILD_GAME_V1]",
    )

    result = _enforce_required_evidence(
        executor,
        project,
        task,
        {"mode": "execute", "exit_code": 0, "stderr": ""},
    )

    assert result["exit_code"] == 65
    assert result["evidence_gate"] == {
        "required": True,
        "passed": False,
        "artifact": ".devpilot/build-game.md",
        "reason": "required_artifact_missing",
    }
    assert "EVIDENCE_GATE_FAILED" in result["stderr"]


def test_build_game_success_is_accepted_with_required_evidence(tmp_path):
    evidence = tmp_path / ".devpilot" / "build-game.md"
    evidence.parent.mkdir()
    evidence.write_text("# Plano\n\nCritérios e evidências.\n", encoding="utf-8")

    executor = SimpleNamespace(repository_path=lambda _project: tmp_path)
    project = SimpleNamespace()
    task = SimpleNamespace(
        title="[Jogo] Gate 1 · Verificar entrega real",
        prompt="[DEVPILOT_DELIVERY_VERIFIER_V1]",
    )

    result = _enforce_required_evidence(
        executor,
        project,
        task,
        {"mode": "execute", "exit_code": 0, "stderr": ""},
    )

    assert result["exit_code"] == 0
    assert result["evidence_gate"]["passed"] is True


def test_real_codex_error_is_not_hidden_by_benign_stderr():
    result = _combine_failure_streams(
        {
            "exit_code": 1,
            "stderr": "Reading additional input from stdin...",
            "stdout": "invalid_request_error: model not supported",
        }
    )

    assert "Reading additional input from stdin" in result["stderr"]
    assert "invalid_request_error" in result["stderr"]
    assert "model not supported" in result["stderr"]
