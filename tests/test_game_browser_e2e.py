import os
from pathlib import Path
import socket
import subprocess
import sys
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


def _wait_health(base_url: str, process: subprocess.Popen, timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"DevPilot E2E server exited early with code {process.returncode}")
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # pragma: no cover - only useful on startup failure
            last_error = str(exc)
        time.sleep(0.2)
    raise AssertionError(f"DevPilot E2E server did not become healthy: {last_error}")


@pytest.fixture()
def e2e_server(tmp_path):
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    data_dir = tmp_path / "data"
    runtime_dir = tmp_path / "runtime"
    env = os.environ.copy()
    env.update(
        {
            "DEVPILOT_ENV": "development",
            "DEVPILOT_DATABASE_URL": f"sqlite:///{tmp_path / 'e2e.db'}",
            "DEVPILOT_DATA_DIR": str(data_dir),
            "DEVPILOT_REPOSITORIES_DIR": str(data_dir / "repositories"),
            "DEVPILOT_HOST_ACTIONS_DIR": str(runtime_dir / "host-actions"),
            "DEVPILOT_AUTH_SECRET": "devpilot-browser-e2e-auth-secret-20260826",
            "DEVPILOT_EXECUTION_ENABLED": "false",
            "DEVPILOT_EMBEDDED_WORKER": "false",
        }
    )
    log_path = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results")) / "browser-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_health(base_url, process)
            yield base_url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_login_game_phase_exit_reopen_stays_responsive(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)

    page_errors: list[str] = []
    server_errors: list[str] = []
    api_requests: list[str] = []
    task_posts = 0

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--enable-precise-memory-info", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()

        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        def on_response(response):
            nonlocal task_posts
            url = response.url
            if "/api/" in url:
                api_requests.append(url)
            if response.status >= 500:
                server_errors.append(f"{response.status} {url}")
            if response.request.method == "POST" and "/api/tasks" in url:
                task_posts += 1

        page.on("response", on_response)

        try:
            page.goto(e2e_server, wait_until="domcontentloaded", timeout=20_000)
            page.locator("#auth-email").fill("e2e-game@devpilot.local")
            page.locator("#auth-password").fill("DevPilot-E2E-Password-2026")
            page.locator("#auth-submit").click()
            page.wait_for_function(
                "() => document.querySelector('#auth-modal')?.open === false",
                timeout=15_000,
            )
            page.wait_for_function(
                "() => Boolean(localStorage.getItem('devpilot-token'))",
                timeout=5_000,
            )

            project = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/projects', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
                    body: JSON.stringify({
                      name: 'Game E2E Project',
                      slug: 'game-e2e-project',
                      description: 'Validar o ciclo real do modo jogo sem congelamento.',
                      repository_url: 'https://github.com/example/devpilot-game-e2e.git',
                      default_branch: 'main'
                    })
                  });
                  if (!response.ok) throw new Error(`project create HTTP ${response.status}`);
                  return await response.json();
                }"""
            )
            assert project.get("id")

            game_entry = page.locator("[data-open-game-entry]")
            game_entry.wait_for(state="visible", timeout=10_000)
            game_entry.click()
            page.wait_for_selector("#build-game-view", state="visible", timeout=15_000)
            page.wait_for_function(
                "() => document.body.classList.contains('devpilot-game-mode')",
                timeout=10_000,
            )

            page.locator("#build-game-goal").fill("Executar o smoke E2E real do modo jogo")
            first_phase = page.locator("#build-game-view [data-play-phase]").first
            first_phase.wait_for(state="visible", timeout=10_000)
            first_phase.click()
            page.wait_for_function("() => document.querySelector('#build-game-view') !== null")
            deadline = time.monotonic() + 8
            while task_posts < 1 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert task_posts == 1, f"expected exactly one phase task POST, got {task_posts}"

            initial_runtime = page.evaluate(
                "() => window.DevPilotGameShell?.metrics?.() || null"
            )
            assert initial_runtime is not None, "game runtime metrics unavailable"
            assert initial_runtime["baseLoads"] >= 1, "base game was never loaded"

            initial_heap = page.evaluate(
                "() => performance.memory?.usedJSHeapSize ?? null"
            )
            initial_request_count = len(api_requests)

            for _ in range(3):
                page.locator(".devpilot-game-exit").click()
                page.wait_for_function(
                    "() => !document.body.classList.contains('devpilot-game-mode')",
                    timeout=5_000,
                )
                game_entry = page.locator("[data-open-game-entry]")
                game_entry.wait_for(state="visible", timeout=5_000)
                game_entry.click()
                page.wait_for_function(
                    "() => document.body.classList.contains('devpilot-game-mode')",
                    timeout=8_000,
                )
                page.wait_for_timeout(250)

            page.wait_for_timeout(1500)
            final_runtime = page.evaluate(
                "() => window.DevPilotGameShell?.metrics?.() || null"
            )
            final_heap = page.evaluate(
                "() => performance.memory?.usedJSHeapSize ?? null"
            )
            extra_requests = len(api_requests) - initial_request_count

            assert final_runtime is not None, "game runtime metrics unavailable after reentry"
            assert final_runtime["baseLoads"] == initial_runtime["baseLoads"], (
                "returning to game reloaded the base runtime: "
                f"{initial_runtime['baseLoads']} -> {final_runtime['baseLoads']}"
            )
            assert final_runtime["resumes"] >= initial_runtime["resumes"] + 3, (
                "expected three lightweight game resumes without base reload"
            )
            assert not page_errors, f"JavaScript errors during game lifecycle: {page_errors}"
            assert not server_errors, f"HTTP 5xx during game lifecycle: {server_errors}"
            assert extra_requests <= 12, f"possible request storm: {extra_requests} API requests after initial game entry"
            if initial_heap is not None and final_heap is not None:
                growth = final_heap - initial_heap
                assert growth < 48 * 1024 * 1024, f"possible browser memory leak: heap grew by {growth} bytes"
        except Exception:
            page.screenshot(path=str(artifact_dir / "game-browser-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
