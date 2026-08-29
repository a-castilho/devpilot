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


def test_tasks_layout_is_readable_at_1024x768(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    page_errors: list[str] = []
    server_errors: list[str] = []

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1024, "height": 768})
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

            created = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const headers = {'Content-Type': 'application/json', Authorization: `Bearer ${token}`};
                  const nonce = Date.now().toString(36);
                  const projectResponse = await fetch('/api/projects', {
                    method: 'POST', headers,
                    body: JSON.stringify({
                      name: `Compact Layout ${nonce}`,
                      slug: `compact-layout-${nonce}`,
                      description: 'Regression fixture for the 1024px compact dashboard.',
                      repository_url: `https://github.com/example/compact-layout-${nonce}.git`,
                      default_branch: 'main'
                    })
                  });
                  if (!projectResponse.ok) throw new Error(`project HTTP ${projectResponse.status}`);
                  const project = await projectResponse.json();
                  const taskResponse = await fetch('/api/tasks', {
                    method: 'POST', headers,
                    body: JSON.stringify({
                      project_id: project.id,
                      title: '[Layout] validar desktop compacto em 1024 pixels',
                      prompt: 'Validar a geometria visual sem executar código.',
                      source: 'dashboard', priority: 78, requires_approval: true
                    })
                  });
                  if (!taskResponse.ok) throw new Error(`task HTTP ${taskResponse.status}`);
                  return {project, task: await taskResponse.json()};
                }"""
            )
            assert created["project"]["id"]
            assert created["task"]["id"]

            page.locator('.nav[data-view="tasks"]').click()
            page.wait_for_selector("#tasks-view.active", timeout=10_000)
            page.wait_for_function(
                "() => document.querySelector('#page-title')?.textContent?.trim() === 'Desenvolvimento'",
                timeout=10_000,
            )
            page.wait_for_function(
                "() => document.querySelector('#tasks-table')?.textContent?.includes('[Layout] validar desktop compacto')",
                timeout=15_000,
            )
            page.wait_for_selector("#tasks-view th[data-task-flow-header]", state="visible", timeout=15_000)
            page.wait_for_selector("#tasks-view td.task-flow-cell", state="visible", timeout=15_000)

            geometry = page.evaluate(
                """() => {
                  const title = document.querySelector('#page-title');
                  const titleLane = document.querySelector('main > header > div:first-child');
                  const actions = document.querySelector('main > header .header-actions');
                  const wrapper = document.querySelector('#tasks-view .table-wrap');
                  const table = wrapper?.querySelector('table');
                  const flowHeader = document.querySelector('#tasks-view th[data-task-flow-header]');
                  const flowCell = document.querySelector('#tasks-view td.task-flow-cell');
                  const actionButtons = [...document.querySelectorAll('#tasks-view tbody tr.task-main-row td button')];
                  const titleStyle = getComputedStyle(title);
                  const actionStyles = actionButtons.map(button => getComputedStyle(button));
                  const titleRect = title.getBoundingClientRect();
                  const titleLaneRect = titleLane.getBoundingClientRect();
                  const actionsRect = actions.getBoundingClientRect();
                  return {
                    viewportWidth: window.innerWidth,
                    documentWidth: document.documentElement.scrollWidth,
                    titleText: title.textContent.trim(),
                    titleHeight: titleRect.height,
                    titleWhiteSpace: titleStyle.whiteSpace,
                    titleWordBreak: titleStyle.wordBreak,
                    titleOverflowWrap: titleStyle.overflowWrap,
                    actionsTop: actionsRect.top,
                    titleLaneBottom: titleLaneRect.bottom,
                    wrapperClientWidth: wrapper.clientWidth,
                    wrapperScrollWidth: wrapper.scrollWidth,
                    tableWidth: table.getBoundingClientRect().width,
                    flowHeaderWidth: flowHeader.getBoundingClientRect().width,
                    flowCellWidth: flowCell.getBoundingClientRect().width,
                    buttonWhiteSpace: actionStyles.map(style => style.whiteSpace),
                  };
                }"""
            )

            assert geometry["viewportWidth"] == 1024
            assert geometry["documentWidth"] <= geometry["viewportWidth"] + 1
            assert geometry["titleText"] == "Desenvolvimento"
            assert geometry["titleHeight"] < 40
            assert geometry["titleWhiteSpace"] == "nowrap"
            assert geometry["titleWordBreak"] == "normal"
            assert geometry["titleOverflowWrap"] == "normal"
            assert geometry["actionsTop"] >= geometry["titleLaneBottom"] - 1
            assert geometry["wrapperScrollWidth"] > geometry["wrapperClientWidth"]
            assert geometry["tableWidth"] >= 1180
            assert geometry["flowHeaderWidth"] >= 250
            assert geometry["flowCellWidth"] >= 250
            assert geometry["buttonWhiteSpace"]
            assert all(value == "nowrap" for value in geometry["buttonWhiteSpace"])
            assert not page_errors, f"JavaScript errors during compact layout flow: {page_errors}"
            assert not server_errors, f"HTTP 5xx during compact layout flow: {server_errors}"
        except Exception:
            page.screenshot(path=str(artifact_dir / "compact-layout-1024-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
