#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def redact_command(command: str) -> str:
    value = command.strip()[:5000]
    patterns = (
        (r"(?i)(authorization\s*:\s*bearer\s+)[^\s'\"]+", r"\1***"),
        (r"(?i)(--(?:password|passwd|token|api[-_]?key|secret)(?:=|\s+))[^\s'\"]+", r"\1***"),
        (r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY)[A-Z0-9_]*)=([^\s]+)", r"\1=***"),
        (r"\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{12,})\b", "***"),
        (r"(https?://)[^/@\s:]+:[^/@\s]+@", r"\1***:***@"),
    )
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    return value


def sanitize_cwd(cwd: str) -> str:
    return re.sub(r"^/home/[^/]+", "~", cwd.strip())[:500]


def read_env_value(path: Path, name: str) -> str:
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            return value.strip().strip("'\"")
    except (OSError, UnicodeError):
        return ""
    return ""


def resolve_token() -> str:
    token = os.getenv("DEVPILOT_BOOTSTRAP_TOKEN", "").strip()
    if token:
        return token

    home = Path(
        os.getenv(
            "DEVPILOT_HOME",
            str(Path.home() / "Documents" / "devpilot"),
        )
    ).expanduser()

    for name in (".env.local", ".env"):
        token = read_env_value(home / name, "DEVPILOT_BOOTSTRAP_TOKEN")
        if token:
            return token

    return ""


def candidate_urls() -> list[str]:
    configured = os.getenv("DEVPILOT_URL", "").strip().rstrip("/")
    if configured:
        return [configured]

    # Docker/desktop local padrão atual. Mantemos 8081 apenas como fallback
    # para instalações antigas ainda não migradas.
    return [
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ]


def send(base_url: str, token: str, payload: dict[str, object]) -> bool:
    request = urllib.request.Request(
        f"{base_url}/api/telemetry/terminal/command",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            response.read(256)
        return True
    except urllib.error.HTTPError as exc:
        # 404/409 normalmente significam que não existe sessão ativa; não é
        # erro operacional do hook e não deve poluir o terminal.
        if exc.code in {404, 409}:
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return False


def main() -> int:
    token = resolve_token()
    command = os.getenv("DEVPILOT_CAPTURE_COMMAND", "").strip()
    if not token or not command:
        return 0

    command = redact_command(command)
    if not command or "devpilot_terminal_capture" in command:
        return 0

    try:
        exit_code = int(os.getenv("DEVPILOT_CAPTURE_EXIT_CODE", "0"))
    except ValueError:
        exit_code = 0

    payload = {
        "command": command,
        "cwd": sanitize_cwd(os.getenv("DEVPILOT_CAPTURE_CWD", "")),
        "shell": os.getenv("DEVPILOT_CAPTURE_SHELL", "bash")[:30],
        "exit_code": exit_code,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }

    for base_url in candidate_urls():
        if send(base_url, token, payload):
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
