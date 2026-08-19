from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _command_version(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0] if output else f"exit={result.returncode}"
    return result.returncode == 0, detail


def _ollama_check() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.ollama_chat_enabled:
        return False, "Ollama chat disabled by configuration"
    try:
        response = httpx.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=min(settings.model_timeout_seconds, 10.0),
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return False, f"unavailable: {error}"

    models = {
        str(item.get("name", ""))
        for item in payload.get("models", [])
        if isinstance(item, dict)
    }
    configured = settings.ollama_chat_model
    if configured in models:
        return True, f"{configured} available"
    return False, f"configured model {configured!r} not found; installed={sorted(models)[:8]}"


def checks() -> list[Check]:
    settings = get_settings()
    git_ok, git_detail = _command_version(["git", "--version"])
    codex_ok, codex_detail = _command_version(["codex", "--version"])
    ollama_ok, ollama_detail = _ollama_check()

    python_ok = sys.version_info >= (3, 12)
    repository_dir_ok = settings.repositories_dir.exists() and settings.repositories_dir.is_dir()
    return [
        Check("python", python_ok, sys.version.split()[0]),
        Check("git", git_ok, git_detail),
        Check(
            "codex",
            codex_ok,
            codex_detail,
            required=settings.execution_enabled and settings.task_executor in {"auto", "codex"},
        ),
        Check(
            "ollama",
            ollama_ok,
            ollama_detail,
            required=(
                settings.execution_enabled
                and settings.local_readonly_enabled
                and settings.task_executor in {"auto", "ollama"}
            ),
        ),
        Check(
            "repositories_dir",
            repository_dir_ok,
            str(settings.repositories_dir.resolve()),
        ),
        Check(
            "execution",
            True,
            json.dumps(
                {
                    "enabled": settings.execution_enabled,
                    "task_executor": settings.task_executor,
                    "local_readonly": settings.local_readonly_enabled,
                },
                ensure_ascii=False,
            ),
            required=False,
        ),
    ]


def main() -> None:
    items = checks()
    for item in items:
        mark = "OK" if item.ok else ("FAIL" if item.required else "WARN")
        print(f"[{mark}] {item.name}: {item.detail}")
    if any(item.required and not item.ok for item in items):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
