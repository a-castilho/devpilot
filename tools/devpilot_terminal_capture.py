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


def resolve_token() -> str:
    # Telemetry is a normal authenticated API. Never reuse the bootstrap secret
    # here: bootstrap credentials are intentionally restricted to auth bootstrap.
    return os.getenv("DEVPILOT_TELEMETRY_TOKEN", "").strip()


def candidate_urls() -> list[str]:
    configured = os.getenv("DEVPILOT_URL", "").strip().rstrip("/")
    return [configured or "http://127.0.0.1:8080"]


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
        # Authentication failures must stop this capture attempt instead of
        # producing fallback traffic/log churn. 404/409 are also benign here:
        # they normally mean there is no active telemetry session.
        if exc.code in {401, 403, 404, 409}:
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return False


def main() -> int:
    if os.getenv("DEVPILOT_TERMINAL_CAPTURE", "0").strip() != "1":
        return 0

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
