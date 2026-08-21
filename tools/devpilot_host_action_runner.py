#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("DEVPILOT_ROOT", Path.home() / "Documents" / "devpilot")).resolve()
DEPLOY_ROOT = Path(os.environ.get("DEVPILOT_DEPLOY_ROOT", Path.home() / "Documents")).expanduser().resolve()
QUEUE_ROOT = Path(os.environ.get("DEVPILOT_HOST_ACTIONS_DIR", ROOT / "runtime" / "host-actions")).resolve()
PENDING = QUEUE_ROOT / "pending"
PROCESSED = QUEUE_ROOT / "processed"
FAILED = QUEUE_ROOT / "failed"
ALLOWED = {"update_local", "manual_deploy"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def finish(source: Path, destination_dir: Path, payload: dict, *, status: str, detail: str) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    payload["finished_at"] = now()
    payload["status"] = status
    payload["detail"] = detail[-4000:]
    destination = destination_dir / source.name
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    source.unlink(missing_ok=True)


def _deploy_workdir(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else DEPLOY_ROOT / raw
    resolved = candidate.resolve()
    try:
        resolved.relative_to(DEPLOY_ROOT)
    except ValueError as error:
        raise ValueError(f"workdir fora da raiz permitida: {DEPLOY_ROOT}") from error
    if not resolved.is_dir():
        raise ValueError(f"workdir inexistente: {resolved}")
    return resolved


def run_manual_deploy(payload: dict) -> tuple[int, str]:
    command = str(payload.get("command") or "").strip()
    if not command:
        return 2, "deploy_command_missing"

    try:
        workdir = _deploy_workdir(str(payload.get("workdir") or ""))
    except ValueError as error:
        return 2, str(error)

    try:
        timeout = int(payload.get("timeout_seconds") or 900)
    except (TypeError, ValueError):
        timeout = 900
    timeout = min(max(timeout, 30), 3600)

    env = {
        **os.environ,
        "DEVPILOT_ROOT": str(ROOT),
        "DEVPILOT_DEPLOY_ROOT": str(DEPLOY_ROOT),
        "DEVPILOT_DEPLOY_PROJECT_ID": str(payload.get("project_id") or ""),
        "DEVPILOT_DEPLOY_PROJECT": str(payload.get("project_name") or ""),
        "DEVPILOT_DEPLOY_ENV": str(payload.get("environment") or ""),
        "DEVPILOT_DEPLOY_BRANCH": str(payload.get("branch") or ""),
    }

    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=workdir,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
        detail = "\n".join(
            part for part in (str(stdout).strip(), str(stderr).strip()) if part
        )
        return 124, f"deploy_timeout_after_{timeout}s\n{detail}".strip()

    detail = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    return result.returncode, detail or f"exit_code={result.returncode}"


def process(request_file: Path) -> None:
    try:
        payload = json.loads(request_file.read_text(encoding="utf-8"))
    except Exception as error:
        finish(request_file, FAILED, {"id": request_file.stem}, status="failed", detail=f"invalid_request: {error}")
        return

    action = str(payload.get("action") or "")
    if action not in ALLOWED:
        finish(request_file, FAILED, payload, status="failed", detail=f"action_not_allowed: {action}")
        return

    payload["status"] = "running"
    payload["started_at"] = now()

    if action == "update_local":
        result = subprocess.run(
            ["bash", str(ROOT / "tools" / "devpilot_local_update.sh")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "DEVPILOT_ROOT": str(ROOT)},
        )
        returncode = result.returncode
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    elif action == "manual_deploy":
        returncode, detail = run_manual_deploy(payload)
    else:
        finish(request_file, FAILED, payload, status="failed", detail=f"unsupported_action: {action}")
        return

    if returncode == 0:
        finish(request_file, PROCESSED, payload, status="completed", detail=detail or "ok")
    else:
        finish(request_file, FAILED, payload, status="failed", detail=detail or f"exit_code={returncode}")


def main() -> int:
    PENDING.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FAILED.mkdir(parents=True, exist_ok=True)
    for request_file in sorted(PENDING.glob("*.json")):
        process(request_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
