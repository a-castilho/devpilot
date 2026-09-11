from __future__ import annotations

import re

from app.models import Project, Task
from app.services import executor

_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_PHASE_6 = re.compile(r"(?mi)^FASE:\s*6/7\s*$")
_SECRET_VALUE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[\"']?[^\s\"']{12,}"
)
_BLOCKED_PATH_PARTS = (
    ".env",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".p12",
    ".pfx",
    "credentials.json",
)


def is_publish_phase(task: Task) -> bool:
    prompt = str(task.prompt or "")
    return _GAME_MARKER in prompt and bool(_PHASE_6.search(prompt))


def _safe_status_paths(repository) -> tuple[bool, str]:
    result = executor.run(["git", "status", "--porcelain"], cwd=repository)
    if result.returncode:
        return False, result.stderr.strip() or "Unable to inspect Git status"
    for raw in result.stdout.splitlines():
        relative = raw[3:].strip().casefold()
        if any(part in relative for part in _BLOCKED_PATH_PARTS):
            return False, f"blocked sensitive path: {relative}"
    return True, result.stdout


def _safe_diff(repository) -> tuple[bool, str]:
    unstaged = executor.run(["git", "diff", "--binary"], cwd=repository)
    staged = executor.run(["git", "diff", "--cached", "--binary"], cwd=repository)
    if unstaged.returncode or staged.returncode:
        return False, "Unable to inspect delivery diff"
    text = f"{unstaged.stdout}\n{staged.stdout}"
    if _SECRET_VALUE.search(text):
        return False, "possible secret detected in delivery diff"
    return True, text


def publish_build_game_phase(project: Project, task: Task, result: dict) -> dict:
    """Publish the explicitly authorized Build Game Git phase without force push.

    The user's Build Game mission is an end-to-end delivery request. Phase 6 is
    therefore the single controlled publication point: changes are scanned, staged,
    committed if needed, and fast-forward pushed to the configured default branch.
    A non-fast-forward or secret finding fails closed and never force-pushes.
    """
    if not is_publish_phase(task) or int(result.get("exit_code", 1)) != 0:
        return result

    repository = executor.ensure_repository(project)
    safe, status = _safe_status_paths(repository)
    if not safe:
        return {
            **result,
            "exit_code": 78,
            "summary": "A publicação automática foi interrompida por uma verificação de segurança.",
            "stderr": status,
        }
    safe, diff = _safe_diff(repository)
    if not safe:
        return {
            **result,
            "exit_code": 78,
            "summary": "A publicação automática foi interrompida por uma verificação de segurança.",
            "stderr": diff,
        }

    if str(status).strip():
        add = executor.run(["git", "add", "-A"], cwd=repository)
        if add.returncode:
            return {**result, "exit_code": add.returncode, "stderr": add.stderr.strip()}
        safe, staged_diff = _safe_diff(repository)
        if not safe:
            executor.run(["git", "reset"], cwd=repository)
            return {
                **result,
                "exit_code": 78,
                "summary": "A publicação automática foi interrompida por uma verificação de segurança.",
                "stderr": staged_diff,
            }
        commit = executor.run(
            ["git", "commit", "-m", f"feat: entrega DevPilot {task.id[:8]}"],
            cwd=repository,
        )
        if commit.returncode:
            return {
                **result,
                "exit_code": commit.returncode,
                "summary": "A etapa Git não conseguiu criar o commit da entrega.",
                "stderr": commit.stderr.strip() or commit.stdout.strip(),
            }

    head = executor.run(["git", "rev-parse", "HEAD"], cwd=repository)
    if head.returncode:
        return {**result, "exit_code": head.returncode, "stderr": head.stderr.strip()}
    commit_sha = head.stdout.strip()

    environment = executor.git_environment(project, project.repository_url)
    target = str(project.default_branch or "main").strip() or "main"
    push = executor.run(
        ["git", "push", "origin", f"HEAD:{target}"],
        cwd=repository,
        timeout=300,
        env_overrides=environment,
    )
    if push.returncode:
        return {
            **result,
            "exit_code": push.returncode,
            "summary": "A publicação Git foi recusada; nenhuma força foi aplicada.",
            "stderr": push.stderr.strip() or push.stdout.strip(),
            "commit_sha": commit_sha,
        }

    result["commit_sha"] = commit_sha
    result["published_branch"] = target
    result["summary"] = (
        "Etapa Git concluída: alterações revisadas, commitadas e publicadas sem force push."
    )
    return result
