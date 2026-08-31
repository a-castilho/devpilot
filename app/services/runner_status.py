from __future__ import annotations

import shutil
import subprocess


SERVICE_NAME = "devpilot-actions-runner.service"
RUNNER_LABEL = "devpilot-ci"


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    if not shutil.which("systemctl"):
        return None
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def runner_status() -> dict[str, object]:
    """Return secret-free health for the host self-hosted GitHub Actions runner.

    This endpoint intentionally describes the GitHub Actions runner only. The
    DevPilot task worker is a different runtime and its activity is derived from
    persisted task/run state by the task observability UI.
    """
    active = _systemctl("is-active", SERVICE_NAME)
    enabled = _systemctl("is-enabled", SERVICE_NAME)

    if active is None:
        return {
            "status": "unknown",
            "online": False,
            "service_enabled": False,
            "service": SERVICE_NAME,
            "label": RUNNER_LABEL,
            "scope": "github_actions",
            "detail": (
                "systemd de usuário não é visível neste runtime; o estado do GitHub Actions Runner "
                "não pôde ser confirmado daqui. Isso não representa o estado do worker de tarefas."
            ),
        }

    is_active = active.returncode == 0 and active.stdout.strip() == "active"
    is_enabled = bool(
        enabled
        and enabled.returncode == 0
        and enabled.stdout.strip() in {"enabled", "enabled-runtime"}
    )

    if is_active:
        detail = "serviço ativo"
        if is_enabled:
            detail += " e habilitado para reinício automático"
        else:
            detail += "; reinício automático ainda não está habilitado"
        status = "online"
    else:
        state = active.stdout.strip() or active.stderr.strip() or "inactive"
        detail = f"serviço {state}; CI pode permanecer aguardando runner"
        status = "offline"

    return {
        "status": status,
        "online": is_active,
        "service_enabled": is_enabled,
        "service": SERVICE_NAME,
        "label": RUNNER_LABEL,
        "scope": "github_actions",
        "detail": detail,
    }
