from __future__ import annotations

from shutil import which


REQUIRED_WORKER_TOOLS = ("git", "codex")


class WorkerRuntimeError(RuntimeError):
    """Raised when the worker image is missing a required runtime executable."""


def worker_runtime_paths(required: tuple[str, ...] = REQUIRED_WORKER_TOOLS) -> dict[str, str]:
    """Resolve required executables without starting background services."""
    paths: dict[str, str] = {}
    missing: list[str] = []

    for tool in required:
        path = which(tool)
        if path:
            paths[tool] = path
        else:
            missing.append(tool)

    if missing:
        tools = ", ".join(missing)
        raise WorkerRuntimeError(
            "Runtime do worker incompleto. Ferramentas ausentes: "
            f"{tools}. Reconstrua a imagem do DevPilot antes de processar tarefas."
        )

    return paths
