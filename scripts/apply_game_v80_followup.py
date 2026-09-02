from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def patch_new_round_intent() -> None:
    path = "app/static/game/development-continuity.js"
    text = read(path)
    old = '''  function newRoundIntentProject() {\n    return String(sessionStorage.getItem(NEW_ROUND_INTENT_KEY) || '').trim();\n  }\n\n  function markNewRoundIntent() {\n    const state = engine()?.snapshot?.();\n    if (state?.projectId) sessionStorage.setItem(NEW_ROUND_INTENT_KEY, String(state.projectId));\n  }\n\n  function clearNewRoundIntentWhenStarted(state) {\n    if (!state?.hasTasks) return;\n    if (newRoundIntentProject() === String(state.projectId || '')) {\n      sessionStorage.removeItem(NEW_ROUND_INTENT_KEY);\n    }\n  }\n\n  async function repairStaleMission(state) {\n    if (!state?.projectId || state.hasTasks || staleRepairBusy || switchBusy) return;\n    if (newRoundIntentProject() === String(state.projectId)) return;\n'''
    new = '''  function hasNewRoundIntent() {\n    return sessionStorage.getItem(NEW_ROUND_INTENT_KEY) === '1';\n  }\n\n  function markNewRoundIntent() {\n    sessionStorage.setItem(NEW_ROUND_INTENT_KEY, '1');\n  }\n\n  function clearNewRoundIntentWhenStarted(state) {\n    if (state?.hasTasks) sessionStorage.removeItem(NEW_ROUND_INTENT_KEY);\n  }\n\n  async function repairStaleMission(state) {\n    if (!state?.projectId || state.hasTasks || staleRepairBusy || switchBusy) return;\n    if (hasNewRoundIntent()) return;\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "function hasNewRoundIntent()" not in text:
        raise RuntimeError("new-round intent block not found")
    write(path, text)


def write_browser_e2e() -> None:
    write(
        "tests/test_game_browser_e2e.py",
        r'''import os
from pathlib import Path
import time

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
    page.locator("#auth-email").wait_for(state="visible", timeout=10_000)
    page.locator("#auth-email").fill(E2E_EMAIL)
    page.locator("#auth-password").fill(E2E_PASSWORD)
    page.locator("#auth-submit").click()
    page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)


def test_game_continues_development_across_projects_without_duplicate_execution(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    page_errors: list[str] = []
    server_errors: list[str] = []
    task_posts = 0

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--enable-precise-memory-info", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        def on_response(response):
            nonlocal task_posts
            if response.status >= 500:
                server_errors.append(f"{response.status} {response.url}")
            if response.request.method == "POST" and "/api/tasks" in response.url:
                task_posts += 1

        page.on("response", on_response)

        try:
            _login(page, e2e_server)
            projects = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const headers = {'Content-Type': 'application/json', Authorization: `Bearer ${token}`};
                  const stamp = Date.now();
                  const specs = [
                    ['Continuity A', `game-continuity-a-${stamp}`],
                    ['Continuity B', `game-continuity-b-${stamp}`],
                  ];
                  const rows = [];
                  for (const [name, slug] of specs) {
                    const response = await fetch('/api/projects', {
                      method: 'POST', headers,
                      body: JSON.stringify({
                        name, slug,
                        description: 'Projeto para validar continuidade real do modo jogo.',
                        repository_url: `https://github.com/example/${slug}.git`,
                        default_branch: 'main'
                      })
                    });
                    if (!response.ok) throw new Error(`project create HTTP ${response.status}`);
                    rows.push(await response.json());
                  }
                  return rows;
                }"""
            )
            project_a, project_b = projects
            assert project_a.get("id") and project_b.get("id")

            page.evaluate(
                "id => { localStorage.setItem('devpilot-build-game-project', id); localStorage.removeItem('devpilot-build-game-mission'); }",
                str(project_a["id"]),
            )
            page.goto(f"{e2e_server}/game/index.html", wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_selector('body[data-devpilot-game-standalone="1"]', timeout=10_000)
            page.wait_for_selector("[data-game73-start]", state="visible", timeout=20_000)
            page.wait_for_function(
                "id => window.__devpilotGameControllerV73?.snapshot?.().projectId === id",
                arg=str(project_a["id"]), timeout=10_000,
            )

            page.locator("[data-game73-goal]").fill("Criar autenticação com perfis para o Projeto A")
            page.locator("[data-game73-start]").click()
            deadline = time.monotonic() + 8
            while task_posts < 1 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert task_posts == 1
            page.wait_for_selector("[data-game80-project-switch]", state="visible", timeout=12_000)

            # Troca para B: não existe rodada anterior, então o jogo oferece uma nova entrega.
            page.locator("[data-game80-project-switch]").select_option(str(project_b["id"]))
            page.wait_for_selector("[data-game73-start]", state="visible", timeout=12_000)
            page.wait_for_function(
                "id => window.__devpilotGameControllerV73?.snapshot?.().projectId === id",
                arg=str(project_b["id"]), timeout=10_000,
            )
            page.locator("[data-game73-goal]").fill("Criar endpoint de relatórios para o Projeto B")
            page.locator("[data-game73-start]").click()
            deadline = time.monotonic() + 8
            while task_posts < 2 and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            assert task_posts == 2
            page.wait_for_selector("[data-game80-project-switch]", state="visible", timeout=12_000)

            # Volta a A: a rodada existente deve ser retomada, sem criar uma terceira execução.
            page.locator("[data-game80-project-switch]").select_option(str(project_a["id"]))
            page.wait_for_function(
                "id => { const s = window.__devpilotGameControllerV73?.snapshot?.(); return s?.projectId === id && s?.hasTasks && s?.goal?.includes('Projeto A'); }",
                arg=str(project_a["id"]), timeout=12_000,
            )
            page.wait_for_timeout(2_000)
            assert task_posts == 2, f"project resume created duplicate task: {task_posts}"

            # Nova rodada é uma intenção explícita: não pode ser anulada pela recuperação do histórico.
            page.locator("[data-game73-new]").click()
            page.wait_for_selector("[data-game73-start]", state="visible", timeout=10_000)
            page.wait_for_timeout(3_000)
            state = page.evaluate("() => window.__devpilotGameControllerV73?.snapshot?.()")
            assert state and state.get("projectId") == str(project_a["id"])
            assert not state.get("hasTasks")
            assert task_posts == 2

            assert not page_errors, f"JavaScript errors: {page_errors}"
            assert not server_errors, f"HTTP 5xx: {server_errors}"
        except Exception:
            page.screenshot(path=str(artifact_dir / "game-v80-browser-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
''',
    )


def extend_v80_contracts() -> None:
    path = "tests/test_game_development_continuity_v80.py"
    text = read(path)
    if "test_delivery_mode_classifier_is_functional" not in text:
        text += r'''


def test_delivery_mode_classifier_is_functional():
    import json
    from app.frontend_ui_routes import _project_delivery_mode

    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["saas"], "frontend": ["react"]}})) == "web"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["api"], "frontend": ["none"]}})) == "service"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["cli"], "frontend": ["none"]}})) == "code"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["automation"], "frontend": ["none"]}})) == "code"


def test_v80_keeps_visible_fallback_and_sequential_dedup_guards():
    index = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
    guard = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
    assert "data-game-critical-boot-v80" in index
    assert "Preparando Modo Jogo" in index
    assert "window.__devpilotGameCreateSequentialDedup = true" in guard
    assert "recentCreations" in guard
    assert "action-runtime.js" not in BOOT.split("const ENTRY_ASSETS = [", 1)[1].split("];", 1)[0]


def test_explicit_new_round_suppresses_history_resume_until_start():
    assert "function hasNewRoundIntent()" in CONTINUITY
    assert "sessionStorage.setItem(NEW_ROUND_INTENT_KEY, '1')" in CONTINUITY
    assert "if (hasNewRoundIntent()) return" in CONTINUITY
    assert "if (state?.hasTasks) sessionStorage.removeItem(NEW_ROUND_INTENT_KEY)" in CONTINUITY
'''
        write(path, text)


def main() -> None:
    patch_new_round_intent()
    write_browser_e2e()
    extend_v80_contracts()
    print("GAME_V80_FOLLOWUP=OK")


if __name__ == "__main__":
    main()
