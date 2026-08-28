import os
from pathlib import Path
import socket
import threading
import time

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
]


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


@pytest.fixture()
def e2e_server(tmp_path, monkeypatch):
    # The self-hosted runner has little RAM. Keeping Uvicorn in the pytest process
    # avoids duplicating the Python application memory and prevents OOM SIGKILLs.
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    data_dir = tmp_path / "data"
    runtime_dir = tmp_path / "runtime"
    test_env = {
        "DEVPILOT_ENV": "development",
        "DEVPILOT_DATABASE_URL": f"sqlite:///{tmp_path / 'e2e.db'}",
        "DEVPILOT_DATA_DIR": str(data_dir),
        "DEVPILOT_REPOSITORIES_DIR": str(data_dir / "repositories"),
        "DEVPILOT_HOST_ACTIONS_DIR": str(runtime_dir / "host-actions"),
        "DEVPILOT_AUTH_SECRET": "devpilot-browser-e2e-auth-secret-20260826",
        "DEVPILOT_EXECUTION_ENABLED": "false",
        "DEVPILOT_EMBEDDED_WORKER": "false",
    }
    for name, value in test_env.items():
        monkeypatch.setenv(name, value)

    # Import after the isolated environment is installed so application settings
    # use the temporary E2E database and directories.
    import uvicorn

    from app.main import app

    log_path = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results")) / "browser-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("server_mode=in_process\n", encoding="utf-8")

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


def test_login_game_phase_exit_reopen_stays_responsive(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    page_errors: list[str] = []
    server_errors: list[str] = []
    api_requests: list[str] = []
    task_posts = 0

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--enable-precise-memory-info", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        def on_response(response):
            nonlocal task_posts
            if "/api/" in response.url:
                api_requests.append(response.url)
            if response.status >= 500:
                server_errors.append(f"{response.status} {response.url}")
            if response.request.method == "POST" and "/api/tasks" in response.url:
                task_posts += 1

        page.on("response", on_response)

        try:
            page.goto(e2e_server, wait_until="domcontentloaded", timeout=20_000)
            page.locator("#auth-email").fill("e2e-game@devpilot.local")
            page.locator("#auth-password").fill("DevPilot-E2E-Password-2026")
            page.locator("#auth-submit").click()
            page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)

            project = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/projects', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
                    body: JSON.stringify({
                      name: 'Game E2E Project', slug: 'game-e2e-project',
                      description: 'Validar o ciclo real do modo jogo sem congelamento.',
                      repository_url: 'https://github.com/example/devpilot-game-e2e.git', default_branch: 'main'
                    })
                  });
                  if (!response.ok) throw new Error(`project create HTTP ${response.status}`);
                  return await response.json();
                }"""
            )
            assert project.get("id")

            page.goto(f"{e2e_server}/game/index.html", wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_selector('body[data-devpilot-game-standalone="1"]', timeout=10_000)
            page.wait_for_selector("#build-game-view", state="visible", timeout=15_000)
            page.wait_for_function("() => document.querySelector('#build-game-view')?.children.length > 0", timeout=15_000)

            page.locator("#build-game-goal").fill("Executar o smoke E2E real do modo jogo")
            first_phase = page.locator("#build-game-view [data-play-phase]").first
            first_phase.wait_for(state="visible", timeout=10_000)
            first_phase.click()
            deadline = time.monotonic() + 8
            while task_posts < 1 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert task_posts == 1, f"expected exactly one phase task POST, got {task_posts}"

            initial_heap = page.evaluate("() => performance.memory?.usedJSHeapSize ?? null")
            initial_request_count = len(api_requests)

            for _ in range(3):
                page.locator("#game-exit").click()
                page.wait_for_url(f"{e2e_server}/", timeout=10_000)
                page.goto(f"{e2e_server}/game/index.html", wait_until="domcontentloaded", timeout=20_000)
                page.wait_for_selector('body[data-devpilot-game-standalone="1"]', timeout=10_000)
                page.wait_for_function("() => document.querySelector('#build-game-view')?.children.length > 0", timeout=15_000)

            page.wait_for_timeout(500)
            final_heap = page.evaluate("() => performance.memory?.usedJSHeapSize ?? null")
            extra_requests = len(api_requests) - initial_request_count

            assert not page_errors, f"JavaScript errors during game lifecycle: {page_errors}"
            assert not server_errors, f"HTTP 5xx during game lifecycle: {server_errors}"
            assert extra_requests <= 40, f"possible request storm: {extra_requests} API requests after initial game entry"
            if initial_heap is not None and final_heap is not None:
                growth = final_heap - initial_heap
                assert growth < 64 * 1024 * 1024, f"possible browser memory leak: heap grew by {growth} bytes"
        except Exception:
            page.screenshot(path=str(artifact_dir / "game-browser-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
