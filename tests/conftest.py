from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
import time

import httpx
import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_health(
    base_url: str,
    server_thread: threading.Thread,
    startup_errors: list[str],
    timeout: float = 25.0,
) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if startup_errors:
            raise AssertionError(f"DevPilot E2E server failed during startup: {startup_errors[-1]}")
        if not server_thread.is_alive():
            raise AssertionError("DevPilot E2E server thread exited before becoming healthy")
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # pragma: no cover - startup diagnostic only
            last_error = str(exc)
        time.sleep(0.2)
    raise AssertionError(f"DevPilot E2E server did not become healthy: {last_error}")


def _install_e2e_rag_compat_schema(engine) -> None:
    """Provide the non-vector RAG job table used by browser-only SQLite tests.

    Production RAG schema provisioning is PostgreSQL/pgvector-only by design. The
    browser matrix intentionally uses isolated SQLite to stay cheap on the low-RAM
    runner, so create only the additive job table required by the Super Admin UI.
    This does not emulate embeddings/vector search and cannot mask external RAG work.
    """
    if engine.dialect.name != "sqlite":
        return

    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rag_index_jobs (
                    id VARCHAR(36) PRIMARY KEY,
                    organization_id VARCHAR(36) NOT NULL,
                    project_id VARCHAR(36) NOT NULL,
                    source_type VARCHAR(40) NOT NULL,
                    source_id VARCHAR(255),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    progress_done INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_rag_jobs_scope_status "
                "ON rag_index_jobs (organization_id, project_id, status)"
            )
        )


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory):
    """Run one in-process DevPilot server for the complete browser E2E matrix.

    The self-hosted runner has little RAM. A single session server avoids loading the
    FastAPI application repeatedly for each critical-domain browser contract.
    """
    if os.getenv("DEVPILOT_RUN_BROWSER_E2E") != "1":
        pytest.skip("browser E2E disabled outside CI/explicit run")

    root = tmp_path_factory.mktemp("devpilot-browser-e2e")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    data_dir = root / "data"
    runtime_dir = root / "runtime"
    test_env = {
        "DEVPILOT_ENV": "development",
        "DEVPILOT_DATABASE_URL": f"sqlite:///{root / 'e2e.db'}",
        "DEVPILOT_DATA_DIR": str(data_dir),
        "DEVPILOT_REPOSITORIES_DIR": str(data_dir / "repositories"),
        "DEVPILOT_HOST_ACTIONS_DIR": str(runtime_dir / "host-actions"),
        "DEVPILOT_AUTH_SECRET": "devpilot-browser-e2e-auth-secret-20260828",
        "DEVPILOT_EXECUTION_ENABLED": "false",
        "DEVPILOT_EMBEDDED_WORKER": "false",
    }
    previous = {name: os.environ.get(name) for name in test_env}
    os.environ.update(test_env)

    # Import only after the isolated environment is installed so application settings,
    # DB engine and runtime directories are bound to the E2E session.
    import uvicorn

    from app.db import engine
    from app.main import app

    _install_e2e_rag_compat_schema(engine)

    log_path = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results")) / "browser-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("server_mode=in_process_session\n", encoding="utf-8")

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    startup_errors: list[str] = []

    def run_server() -> None:
        try:
            server.run()
        except BaseException as exc:  # pragma: no cover - diagnostic path
            startup_errors.append(f"{type(exc).__name__}: {exc}")
            with log_path.open("a", encoding="utf-8") as log:
                log.write(startup_errors[-1] + "\n")

    server_thread = threading.Thread(
        target=run_server,
        name="devpilot-e2e-server",
        daemon=True,
    )
    server_thread.start()

    try:
        _wait_health(base_url, server_thread, startup_errors)
        yield base_url
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)
        if server_thread.is_alive():
            server.force_exit = True
            server_thread.join(timeout=2)
        assert not server_thread.is_alive(), "DevPilot E2E server thread did not stop cleanly"
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
