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
    """Return secret-free local health for the self-hosted GitHub Actions runner."""
    active = _systemctl("is-active", SERVICE_NAME)
    enabled = _systemctl("is-enabled", SERVICE_NAME)

    if active is None:
        return {
            "status": "unknown",
            "online": False,
            "service_enabled": False,
            "service": SERVICE_NAME,
            "label": RUNNER_LABEL,
            "detail": "systemd de usuário indisponível; estado do runner não pôde ser confirmado.",
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
        "detail": detail,
    }
