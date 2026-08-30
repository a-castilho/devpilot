import os
from pathlib import Path

import pytest


RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
]


E2E_EMAIL = "e2e-admin@devpilot.local"
E2E_PASSWORD = "DevPilot-E2E-Password-2026"


def _login(page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=20_000)
    page.locator("#auth-email").fill(E2E_EMAIL)
    page.locator("#auth-password").fill(E2E_PASSWORD)
    page.locator("#auth-submit").click()
    page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)
    page.wait_for_function("() => window.__devpilotBoot?.phase === 'ready'", timeout=20_000)


def _resume_saved_session(page) -> None:
    """Confirm the intentionally explicit saved-session handoff after a reload."""
    page.wait_for_selector("#auth-resume", state="visible", timeout=10_000)
    assert page.locator("#auth-resume-submit").is_visible()
    page.locator("#auth-resume-submit").click()
    page.wait_for_function("() => window.__devpilotBoot?.phase === 'ready'", timeout=20_000)
    page.wait_for_function(
        "() => !document.documentElement.classList.contains('devpilot-auth-pending')",
        timeout=10_000,
    )


def test_login_tasks_and_super_admin_critical_flow(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    page_errors: list[str] = []
    server_errors: list[str] = []

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "response",
            lambda response: server_errors.append(f"{response.status} {response.url}")
            if response.status >= 500
            else None,
        )

        try:
            _login(page, e2e_server)

            session = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/auth/me', {
                    headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'
                  });
                  return {status: response.status, body: await response.json()};
                }"""
            )
            assert session["status"] == 200
            assert session["body"]["role"] == "SUPER_ADMIN"

            page.reload(wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=10_000)
            _resume_saved_session(page)

            created = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const headers = {'Content-Type': 'application/json', Authorization: `Bearer ${token}`};
                  const projectResponse = await fetch('/api/projects', {
                    method: 'POST', headers,
                    body: JSON.stringify({
                      name: 'Critical Matrix E2E', slug: 'critical-matrix-e2e',
                      description: 'Fluxo crítico de execuções da matriz de qualidade.',
                      repository_url: 'https://github.com/example/critical-matrix-e2e.git',
                      default_branch: 'main'
                    })
                  });
                  if (!projectResponse.ok) throw new Error(`project HTTP ${projectResponse.status}`);
                  const project = await projectResponse.json();
                  const taskResponse = await fetch('/api/tasks', {
                    method: 'POST', headers,
                    body: JSON.stringify({
                      project_id: project.id,
                      title: 'Execução E2E da matriz crítica',
                      prompt: 'Validar criação e leitura da execução sem executar código.',
                      source: 'dashboard', priority: 80, requires_approval: false
                    })
                  });
                  if (!taskResponse.ok) throw new Error(`task HTTP ${taskResponse.status}`);
                  const task = await taskResponse.json();
                  const deletableResponse = await fetch('/api/tasks', {
                    method: 'POST', headers,
                    body: JSON.stringify({
                      project_id: project.id,
                      title: 'Execução E2E removível',
                      prompt: 'Alterar arquivos somente depois de aprovação explícita.',
                      source: 'dashboard', priority: 70, requires_approval: true
                    })
                  });
                  if (!deletableResponse.ok) throw new Error(`deletable task HTTP ${deletableResponse.status}`);
                  const deletable = await deletableResponse.json();
                  return {project, task, deletable};
                }"""
            )
            assert created["project"]["id"]
            assert created["task"]["id"]
            assert created["deletable"]["id"]
            assert created["deletable"]["status"] == "awaiting_approval"

            # Execuções abre sem pagar o custo de analytics.
            page.locator('.nav[data-view="tasks"]').click()
            page.wait_for_selector("#tasks-view.active", timeout=10_000)
            page.wait_for_function(
                "() => document.querySelector('#tasks-table')?.textContent?.includes('Execução E2E da matriz crítica')",
                timeout=15_000,
            )
            assert page.locator('script[src*="task-analytics.js"]').count() == 0

            # Analytics é estritamente lazy: somente após intenção explícita.
            page.locator('#tasks-v9-indicators').click()
            page.wait_for_selector('script[src*="task-analytics.js"]', state="attached", timeout=15_000)
            page.wait_for_function(
                "() => document.querySelector('script[src*=\"task-analytics.js\"]')?.dataset.devpilotFeatureLoadState === 'loaded'",
                timeout=15_000,
            )
            assert page.locator('script[src*="task-analytics.js"]').count() == 1

            page.wait_for_selector('script[src*="project-delete-ui.js"]', state="attached", timeout=15_000)
            page.wait_for_function(
                "() => document.querySelector('script[src*=\"project-delete-ui.js\"]')?.dataset.devpilotFeatureLoadState === 'loaded'",
                timeout=15_000,
            )

            active_row = page.locator("#tasks-table .task-main-row", has_text="Execução E2E da matriz crítica")
            active_row.wait_for(state="visible", timeout=10_000)
            assert active_row.locator("button.delete-task").count() == 0

            deletable_row = page.locator("#tasks-table .task-main-row", has_text="Execução E2E removível")
            deletable_row.wait_for(state="visible", timeout=10_000)
            delete_button = deletable_row.locator("button.delete-task")
            delete_button.wait_for(state="visible", timeout=10_000)

            page.once("dialog", lambda dialog: dialog.dismiss())
            delete_button.click()
            assert deletable_row.is_visible()
            still_present = page.evaluate(
                """async taskId => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/ui/tasks?limit=20', {
                    headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'
                  });
                  const tasks = await response.json();
                  return {status: response.status, present: tasks.some(item => item.id === taskId)};
                }""",
                created["deletable"]["id"],
            )
            assert still_present == {"status": 200, "present": True}

            page.once("dialog", lambda dialog: dialog.accept())
            with page.expect_response(
                lambda response: response.request.method == "DELETE"
                and f"/api/tasks/{created['deletable']['id']}" in response.url,
                timeout=15_000,
            ) as delete_response_info:
                delete_button.click()
            assert delete_response_info.value.status == 204
            deletable_row.wait_for(state="detached", timeout=10_000)

            persisted = page.evaluate(
                """async ({deletedId, activeId}) => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/ui/tasks?limit=20', {
                    headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'
                  });
                  const tasks = await response.json();
                  return {
                    status: response.status,
                    deletedPresent: tasks.some(item => item.id === deletedId),
                    activePresent: tasks.some(item => item.id === activeId),
                  };
                }""",
                {"deletedId": created["deletable"]["id"], "activeId": created["task"]["id"]},
            )
            assert persisted == {"status": 200, "deletedPresent": False, "activePresent": True}

            blocked_delete = page.evaluate(
                """async taskId => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
                    method: 'DELETE', headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'
                  });
                  return {status: response.status, body: await response.json()};
                }""",
                created["task"]["id"],
            )
            assert blocked_delete["status"] == 409
            assert blocked_delete["body"]["detail"] == "Active task cannot be deleted"

            page.reload(wait_until="domcontentloaded", timeout=20_000)
            _resume_saved_session(page)
            page.locator('.nav[data-view="tasks"]').click()
            page.wait_for_selector("#tasks-view.active", timeout=10_000)
            page.wait_for_function(
                "() => document.querySelector('#tasks-table')?.textContent?.includes('Execução E2E da matriz crítica')",
                timeout=15_000,
            )
            assert page.locator("#tasks-table .task-main-row", has_text="Execução E2E removível").count() == 0
            assert page.locator("#tasks-table .task-main-row", has_text="Execução E2E da matriz crítica").count() == 1

            admin_placeholder = page.locator('[data-devpilot-feature-placeholder="admin"]')
            admin_placeholder.wait_for(state="visible", timeout=10_000)
            admin_placeholder.click()
            page.wait_for_selector(
                'script[src*="super-admin-task-panel.js"]',
                state="attached",
                timeout=15_000,
            )
            page.wait_for_function(
                "() => document.querySelector('script[src*=\"super-admin-task-panel.js\"]')?.dataset.devpilotFeatureLoadState === 'loaded'",
                timeout=15_000,
            )

            clouds = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const response = await fetch('/api/admin/clouds', {
                    headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'
                  });
                  return {status: response.status, body: await response.json()};
                }"""
            )
            assert clouds["status"] == 200
            assert {item["provider"] for item in clouds["body"]} >= {"github", "vercel", "render", "neon"}

            assert not page_errors, f"JavaScript errors during critical flow: {page_errors}"
            assert not server_errors, f"HTTP 5xx during critical flow: {server_errors}"
        except Exception:
            page.screenshot(path=str(artifact_dir / "critical-browser-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
