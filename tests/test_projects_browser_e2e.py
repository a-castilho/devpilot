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


def test_mobile_projects_open_without_main_thread_stall(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifact_dir = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    page_errors: list[str] = []

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            _login(page, e2e_server)

            created = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const headers = {'Content-Type': 'application/json', Authorization: `Bearer ${token}`};
                  const ids = [];
                  for (let index = 0; index < 14; index += 1) {
                    const suffix = `mobile-stall-${index}`;
                    const response = await fetch('/api/projects', {
                      method: 'POST',
                      headers,
                      body: JSON.stringify({
                        name: `Mobile Stall E2E ${index}`,
                        slug: suffix,
                        description: 'Projeto pequeno para validar abertura mobile.',
                        repository_url: `https://github.com/example/${suffix}.git`,
                        default_branch: 'main'
                      })
                    });
                    if (!response.ok) throw new Error(`project HTTP ${response.status}`);
                    ids.push((await response.json()).id);
                  }
                  return ids;
                }"""
            )
            assert len(created) == 14

            with page.expect_response(
                lambda response: "/api/ui/projects?limit=12" in response.url,
                timeout=15_000,
            ) as projects_response:
                page.locator('.nav[data-view="projects"]:visible').first.click()

            assert projects_response.value.status == 200
            page.wait_for_selector("#projects-view.active", timeout=10_000)
            page.wait_for_function(
                """() => {
                  const target = document.querySelector('#projects-list');
                  return target
                    && target.querySelectorAll('.project-card').length > 0
                    && !target.textContent.includes('Carregando projetos');
                }""",
                timeout=15_000,
            )

            card_count = page.locator("#projects-list > .project-card").count()
            assert 1 <= card_count <= 6
            assert page.locator('script[src*="project-ships.js"]').count() == 0
            assert page.locator('script[src*="product-delivery-ui.js"]').count() == 0
            assert page.locator('script[src*="project-builder.js"]').count() == 0

            # Confirma que o event loop continua atendendo timers após a renderização.
            assert page.evaluate(
                "() => new Promise(resolve => setTimeout(() => resolve(true), 100))"
            )

            revision = page.evaluate(
                """() => {
                  const script = document.querySelector('script[src*="mobile-project-card-compact.js"]');
                  return {
                    expected: window.__devpilotAssetRevisions?.['mobile-project-card-compact.js'],
                    actual: script ? new URL(script.src).searchParams.get('v') : null,
                  };
                }"""
            )
            assert revision["expected"]
            assert revision["actual"] == revision["expected"]
            assert not page_errors, f"JavaScript errors during mobile projects flow: {page_errors}"
        except Exception:
            page.screenshot(path=str(artifact_dir / "projects-mobile-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
