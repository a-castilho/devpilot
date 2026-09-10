import os

import pytest


RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
]


def test_controller_advances_through_all_seven_stages_and_gates_before_delivery():
    playwright_api = pytest.importorskip("playwright.sync_api")
    engine_source = open("app/static/build-game.js", encoding="utf-8").read()
    gate_source = open("app/static/game/delivery-gate.js", encoding="utf-8").read()

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()
        page.route(
            "http://game.test/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body><main><section id='build-game-view'></section></main></body></html>",
            ),
        )
        page.goto("http://game.test/", wait_until="domcontentloaded")
        page.evaluate(
            """() => {
              window.state = {projects: [{id: 'project-1', name: 'Seven Stage Project'}]};
              window.toast = () => {};
              window.esc = value => String(value ?? '');
              window.showView = () => {};
              window.__tasks = [];
              window.__taskPosts = [];
              window.__deliveryAutoPosts = 0;
              window.__counter = 0;

              const normalizePath = path => String(path || '');
              window.api = async (path, options = {}) => {
                const requestPath = normalizePath(path);
                const method = String(options.method || 'GET').toUpperCase();

                if (requestPath === '/projects' && method === 'GET') return window.state.projects;
                if ((requestPath.startsWith('/tasks?') || requestPath.startsWith('/ui/game-tasks?')) && method === 'GET') {
                  return window.__tasks.map(task => ({...task}));
                }
                if (requestPath === '/tasks' && method === 'POST') {
                  const payload = JSON.parse(String(options.body || '{}'));
                  window.__counter += 1;
                  const task = {
                    id: `task-${window.__counter}`,
                    title: payload.title,
                    prompt: payload.prompt,
                    status: 'queued',
                    created_at: new Date(Date.now() + window.__counter * 1000).toISOString(),
                  };
                  window.__tasks.unshift(task);
                  window.__taskPosts.push({...task});
                  return {...task};
                }
                if (requestPath === '/projects/project-1/delivery' && method === 'GET') {
                  return {status: window.__deliveryAutoPosts ? 'ready' : 'pending'};
                }
                if (requestPath === '/projects/project-1/delivery/auto' && method === 'POST') {
                  window.__deliveryAutoPosts += 1;
                  return {status: 'ready', url: 'https://example.test/delivery'};
                }
                throw new Error(`unexpected API call: ${method} ${requestPath}`);
              };
            }"""
        )
        page.add_script_tag(content=engine_source)
        page.add_script_tag(content=gate_source)

        started = page.evaluate(
            """async () => window.__devpilotGameControllerV73.startRound({
              projectId: 'project-1',
              goal: 'Provar a esteira completa de sete etapas'
            })"""
        )
        assert started["currentPhaseId"] == 1
        assert started["total"] == 7
        assert page.evaluate("() => window.__taskPosts.length") == 1

        for phase in range(1, 8):
            page.evaluate(
                """phase => {
                  const base = window.__tasks.find(task =>
                    task.prompt.includes(`FASE: ${phase}/7`) &&
                    !task.prompt.includes('[DEVPILOT_DELIVERY_VERIFIER_V1]')
                  );
                  if (!base) throw new Error(`base task missing for phase ${phase}`);
                  base.status = 'completed';
                }""",
                phase,
            )

            page.evaluate("() => window.__devpilotGameControllerV73.refresh()")
            gate = page.evaluate(
                """phase => window.__tasks.find(task =>
                  task.prompt.includes(`FASE: ${phase}/7`) &&
                  task.prompt.includes('[DEVPILOT_DELIVERY_VERIFIER_V1]')
                )""",
                phase,
            )
            assert gate, f"gate was not created for phase {phase}"
            assert gate["status"] == "queued"

            page.evaluate(
                """taskId => {
                  const task = window.__tasks.find(item => item.id === taskId);
                  if (!task) throw new Error(`gate task ${taskId} missing`);
                  task.status = 'completed';
                }""",
                gate["id"],
            )

            page.evaluate("() => window.__devpilotGameControllerV73.refresh()")
            snapshot = page.evaluate("() => window.__devpilotGameControllerV73.snapshot()")
            assert snapshot["completed"] == phase
            assert snapshot["total"] == 7
            if phase < 7:
                assert snapshot["currentPhaseId"] == phase + 1
                assert snapshot["done"] is False
            else:
                assert snapshot["done"] is True
                assert snapshot["completed"] == 7
                assert snapshot["percent"] == 100

        # Delivery is owned by the independent gate runtime and must only become
        # eligible after every phase has a completed verifier.
        page.evaluate("() => window.__devpilotEnsureDeliveryGate()")

        posts = page.evaluate(
            """() => window.__taskPosts.map(task => ({title: task.title, prompt: task.prompt}))"""
        )
        assert len(posts) == 14
        for phase in range(1, 8):
            phase_posts = [item for item in posts if f"FASE: {phase}/7" in item["prompt"]]
            assert len(phase_posts) == 2, f"phase {phase} should have one execution and one gate"
            assert sum("[DEVPILOT_DELIVERY_VERIFIER_V1]" in item["prompt"] for item in phase_posts) == 1

        assert page.evaluate("() => window.__deliveryAutoPosts") == 1

        context.close()
        browser.close()
