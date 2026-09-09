from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

_BUILD_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_DELIVERY_VERIFIER_MARKER = "[DEVPILOT_DELIVERY_VERIFIER_V1]"
_READ_ONLY_MARKER = "[DEVPILOT_MODE=analysis-read-only]"
_REQUIRED_EVIDENCE = Path(".devpilot/build-game.md")
_BENIGN_CODEX_STDERR = "Reading additional input from stdin..."


def _requires_build_game_evidence(task: Any) -> bool:
    title = str(getattr(task, "title", "") or "")
    prompt = str(getattr(task, "prompt", "") or "")
    payload = f"{title}\n{prompt}"
    return (
        _BUILD_GAME_MARKER in payload
        or _DELIVERY_VERIFIER_MARKER in payload
        or title.startswith("[Jogo]")
    )


def _is_read_only_prompt(prompt: str) -> bool:
    text = str(prompt or "")
    return _READ_ONLY_MARKER in text or "This is a READ-ONLY ANALYSIS." in text


def _add_workspace_write(command: list[str]) -> list[str]:
    updated = list(command)
    if "--sandbox" in updated:
        return updated
    try:
        exec_index = updated.index("exec")
    except ValueError:
        return updated
    updated[exec_index + 1:exec_index + 1] = ["--sandbox", "workspace-write"]
    return updated


def _combine_failure_streams(result: dict) -> dict:
    if int(result.get("exit_code") or 0) == 0:
        return result

    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        return result

    if not stderr or stderr == _BENIGN_CODEX_STDERR:
        result["stderr"] = f"{stderr}\n{stdout[-20_000:]}".strip()
    return result


def _enforce_required_evidence(executor_module: Any, project: Any, task: Any, result: dict) -> dict:
    if str(result.get("mode") or "") != "execute":
        return result
    if int(result.get("exit_code") or 0) != 0:
        return result
    if not _requires_build_game_evidence(task):
        return result

    repository = executor_module.repository_path(project)
    evidence = repository / _REQUIRED_EVIDENCE
    try:
        evidence_ok = evidence.is_file() and evidence.stat().st_size > 0
    except OSError:
        evidence_ok = False

    if evidence_ok:
        result["evidence_gate"] = {
            "required": True,
            "passed": True,
            "artifact": str(_REQUIRED_EVIDENCE),
        }
        return result

    diagnostic = f"EVIDENCE_GATE_FAILED: artefato obrigatório ausente: {_REQUIRED_EVIDENCE}"
    stderr = str(result.get("stderr") or "").strip()
    result["exit_code"] = 65
    result["summary"] = (
        "A execução terminou sem materializar a evidência obrigatória "
        f"{_REQUIRED_EVIDENCE}; a tarefa não pode ser concluída."
    )
    result["stderr"] = f"{stderr}\n{diagnostic}".strip()
    result["evidence_gate"] = {
        "required": True,
        "passed": False,
        "artifact": str(_REQUIRED_EVIDENCE),
        "reason": "required_artifact_missing",
    }
    return result


def install_execution_guards() -> None:
    from app.services import executor

    if getattr(executor, "_devpilot_execution_guards_installed", False):
        return

    original_codex_command: Callable[..., list[str]] = executor.codex_command
    original_execute_task: Callable[..., dict] = executor.execute_task

    def guarded_codex_command(project: Any, prompt: str) -> list[str]:
        command = original_codex_command(project, prompt)
        if _is_read_only_prompt(prompt):
            return command
        return _add_workspace_write(command)

    def guarded_execute_task(project: Any, task: Any) -> dict:
        result = original_execute_task(project, task)
        if not isinstance(result, dict):
            return result
        result = _combine_failure_streams(result)
        return _enforce_required_evidence(executor, project, task, result)

    executor.codex_command = guarded_codex_command
    executor.execute_task = guarded_execute_task
    executor._devpilot_execution_guards_installed = True
