import os
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
    page.locator("#auth-email").fill(E2E_EMAIL)
    page.locator("#auth-password").fill(E2E_PASSWORD)
    page.locator("#auth-submit").click()
    page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)
    page.wait_for_function("() => window.__devpilotBoot?.phase === 'ready'", timeout=20_000)


def test_new_project_opens_without_freezing_browser(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    page_errors: list[str] = []

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        try:
            _login(page, e2e_server)

            # Entrar em Projetos e abrir o cadastro precisa trocar a view antes do
            # carregamento do bundle pesado. O limite é propositalmente folgado para CI,
            # mas curto o suficiente para capturar o congelamento observado no Chromium.
            page.evaluate("() => window.devpilotNavigate?.('projects', {source:'e2e', immediate:true})")
            page.wait_for_selector("#projects-view.active", state="visible", timeout=10_000)
            trigger = page.locator('[data-project-builder-open]:visible').first
            trigger.wait_for(state="visible", timeout=10_000)

            started = time.monotonic()
            trigger.click(timeout=3_000)
            page.wait_for_selector("#new-project-view.active", state="visible", timeout=2_500)
            open_elapsed = time.monotonic() - started
            assert open_elapsed < 2.5

            page.wait_for_function("() => Boolean(window.__devpilotProjectBuilderV94)", timeout=10_000)
            page.wait_for_function(
                "() => document.querySelectorAll('#project-builder-groups .choice-card').length > 50",
                timeout=10_000,
            )

            # Os runtimes que criavam uma cadeia oculta menu -> jogo -> builder foram
            # removidos; nenhum deles pode reaparecer durante o fluxo real.
            assert page.locator('script[src*="project-builder-mobile-runtime-v39.js"]').count() == 0
            assert page.locator('script[src*="mobile-game-ships-stable.js"]').count() == 0

            # Uma interação real após a montagem deve continuar respondendo.
            page.locator('[data-builder-preset="api-fast"]').click(timeout=3_000)
            page.locator('#project-builder-form [name="name"]').fill("Projeto E2E V94", timeout=3_000)
            page.locator('#project-builder-form [name="slug"]').fill("projeto-e2e-v94", timeout=3_000)
            page.wait_for_function(
                "() => document.querySelector('#project-builder-selection-count')?.textContent?.includes('escolhas') || document.querySelector('#project-builder-form')?.dataset.mobilePerformanceGuard === '1'",
                timeout=3_000,
            )

            diagnostics = page.evaluate(
                """() => ({
                  builder: window.__devpilotProjectBuilderV94,
                  slow: (window.__devpilotFrontendDiagnostics || [])
                    .filter(item => item.scope === 'new-project' && item.durationMs >= 1000),
                  view: document.documentElement.dataset.devpilotView,
                })"""
            )
            assert diagnostics["builder"]["version"] == "v94"
            assert diagnostics["view"] == "new-project"
            assert diagnostics["slow"] == []
            assert page_errors == []
        finally:
            context.close()
            browser.close()
