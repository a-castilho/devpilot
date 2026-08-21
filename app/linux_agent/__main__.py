from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import uvicorn


def make_socket_available(socket_path: Path) -> None:
    for _ in range(100):
        if socket_path.exists():
            try:
                socket_path.chmod(0o666)
            except OSError:
                pass
            return
        time.sleep(0.05)


def main() -> None:
    socket_raw = os.environ.get("DEVPILOT_LINUX_AGENT_SOCKET", "").strip()
    log_level = os.environ.get("DEVPILOT_LINUX_AGENT_LOG_LEVEL", "info")

    if socket_raw:
        socket_path = Path(socket_raw).expanduser()
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        if socket_path.exists():
            socket_path.unlink()
        threading.Thread(
            target=make_socket_available,
            args=(socket_path,),
            name="devpilot-agent-socket-permissions",
            daemon=True,
        ).start()
        uvicorn.run(
            "app.linux_agent.main:app",
            uds=str(socket_path),
            log_level=log_level,
        )
        return

    host = os.environ.get("DEVPILOT_LINUX_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("DEVPILOT_LINUX_AGENT_PORT", "8787"))
    uvicorn.run(
        "app.linux_agent.main:app",
        host=host,
        port=port,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
