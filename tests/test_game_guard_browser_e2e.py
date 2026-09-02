import os

import pytest


RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
]


def test_guard_keeps_one_post_until_exact_created_task_is_visible():
    playwright_api = pytest.importorskip("playwright.sync_api")
    guard = open("app/static/game/task-payload-guard.js", encoding="utf-8").read()

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()
        page.route("http://game.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body="<html><body></body></html>"))
        page.goto("http://game.test/", wait_until="domcontentloaded")
        page.evaluate(
            """() => {
              window.__postCount = 0;
              window.__showCreated = false;
              window.__createdTask = {
                id: 'task-created-1',
                title: '[Jogo] Etapa 1 · Planejamento',
                status: 'queued',
                prompt: '[DEVPILOT_BUILD_GAME_V1]\\nPARTIDA: mission-1\\nFASE: 1/7\\nOBJETIVO: teste'
              };
              window.api = async (path, options = {}) => {
                const method = String(options.method || 'GET').toUpperCase();
                if (path === '/tasks' && method === 'POST') {
                  window.__postCount += 1;
                  return {...window.__createdTask};
                }
                if (method === 'GET' && (String(path).startsWith('/tasks?') || String(path).startsWith('/ui/game-tasks?'))) {
                  return window.__showCreated ? [{...window.__createdTask}] : [];
                }
                return [];
              };
            }"""
        )
        page.add_script_tag(content=guard)

        payload = {
            "project_id": "project-1",
            "title": "[Jogo] Etapa 1 · Planejamento",
            "prompt": "[DEVPILOT_BUILD_GAME_V1]\nPARTIDA: mission-1\nFASE: 1/7\nOBJETIVO: teste",
        }

        first = page.evaluate(
            """async payload => window.api('/tasks', {method:'POST', body:JSON.stringify(payload)})""",
            payload,
        )
        second = page.evaluate(
            """async payload => window.api('/tasks', {method:'POST', body:JSON.stringify(payload)})""",
            payload,
        )
        assert first["id"] == "task-created-1"
        assert second["id"] == "task-created-1"
        assert page.evaluate("() => window.__postCount") == 1

        page.evaluate("() => window.api('/tasks?project_id=project-1&limit=500')")
        third = page.evaluate(
            """async payload => window.api('/tasks', {method:'POST', body:JSON.stringify(payload)})""",
            payload,
        )
        assert third["id"] == "task-created-1"
        assert page.evaluate("() => window.__postCount") == 1

        page.evaluate("() => { window.__showCreated = true; }")
        page.evaluate("() => window.api('/tasks?project_id=project-1&limit=500')")
        page.evaluate("() => { window.__showCreated = false; }")
        page.evaluate(
            """async payload => window.api('/tasks', {method:'POST', body:JSON.stringify(payload)})""",
            payload,
        )
        assert page.evaluate("() => window.__postCount") == 2
        assert page.evaluate("() => window.__devpilotGameCreateSequentialDedup === true") is True

        context.close()
        browser.close()
