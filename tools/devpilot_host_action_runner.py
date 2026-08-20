#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("DEVPILOT_ROOT", Path.home() / "Documents" / "devpilot")).resolve()
QUEUE_ROOT = Path(os.environ.get("DEVPILOT_HOST_ACTIONS_DIR", ROOT / "runtime" / "host-actions")).resolve()
PENDING = QUEUE_ROOT / "pending"
PROCESSED = QUEUE_ROOT / "processed"
FAILED = QUEUE_ROOT / "failed"
ALLOWED = {"update_local"}


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

    if action == "update_local":
        command = ["bash", str(ROOT / "tools" / "devpilot_local_update.sh")]
    else:
        finish(request_file, FAILED, payload, status="failed", detail=f"unsupported_action: {action}")
        return

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "DEVPILOT_ROOT": str(ROOT)},
    )
    detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if result.returncode == 0:
        finish(request_file, PROCESSED, payload, status="completed", detail=detail or "ok")
    else:
        finish(request_file, FAILED, payload, status="failed", detail=detail or f"exit_code={result.returncode}")


def main() -> int:
    PENDING.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FAILED.mkdir(parents=True, exist_ok=True)
    for request_file in sorted(PENDING.glob("*.json")):
        process(request_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
