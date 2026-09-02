import os
from pathlib import Path
import time

import pytest


RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
]


def test_login_game_start_exit_reopen_stays_responsive(e2e_server):
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
            page.locator("#auth-email").fill("e2e-admin@devpilot.local")
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

            page.goto(f"{e2e_server}/assets/game/index.html", wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_selector('body[data-devpilot-game-standalone="1"][data-devpilot-game-version="v73"]', timeout=10_000)
            page.wait_for_selector("[data-game73-start]", state="visible", timeout=15_000)
            page.locator("[data-game73-project]").select_option(str(project["id"]))
            page.locator("[data-game73-goal]").fill("Executar o smoke E2E real do modo jogo")
            page.locator("[data-game73-start]").click()

            deadline = time.monotonic() + 10
            while task_posts < 1 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert task_posts == 1, f"expected exactly one initial phase task POST, got {task_posts}"
            page.wait_for_selector(".game73", state="visible", timeout=10_000)
            page.wait_for_function("() => Boolean(window.__devpilotGameControllerV73)", timeout=10_000)

            initial_heap = page.evaluate("() => performance.memory?.usedJSHeapSize ?? null")
            initial_request_count = len(api_requests)

            for _ in range(3):
                page.locator("#game-exit").click()
                page.wait_for_url(f"{e2e_server}/", timeout=10_000)
                page.goto(f"{e2e_server}/assets/game/index.html", wait_until="domcontentloaded", timeout=20_000)
                page.wait_for_selector('body[data-devpilot-game-standalone="1"]', timeout=10_000)
                page.wait_for_selector(".game73", state="visible", timeout=15_000)
                page.wait_for_function("() => Boolean(window.__devpilotGameControllerV73)", timeout=10_000)

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
