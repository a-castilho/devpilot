#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


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


def main() -> int:
    token = os.getenv("DEVPILOT_BOOTSTRAP_TOKEN", "").strip()
    command = os.getenv("DEVPILOT_CAPTURE_COMMAND", "").strip()
    if not token or not command:
        return 0

    command = redact_command(command)
    if not command or "devpilot_terminal_capture" in command:
        return 0

    base_url = os.getenv("DEVPILOT_URL", "http://127.0.0.1:8081").rstrip("/")
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
        with urllib.request.urlopen(request, timeout=2) as response:
            response.read(256)
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
