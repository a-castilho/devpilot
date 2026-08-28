from __future__ import annotations

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUN_BROWSER_E2E = os.getenv("DEVPILOT_RUN_BROWSER_E2E") == "1"
RAG_RUNTIME_PRESENT = (ROOT / "app/rag_admin_routes.py").is_file() and (ROOT / "app/static/rag-admin-ui.js").is_file()

pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(not RUN_BROWSER_E2E, reason="browser E2E disabled outside CI/explicit run"),
    pytest.mark.skipif(not RAG_RUNTIME_PRESENT, reason="RAG runtime not present on this revision"),
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


def test_super_admin_can_open_rag_and_read_health_without_external_calls(e2e_server):
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

            # RAG belongs to the lazy Super Admin bundle. This proves the browser can
            # activate the module through the same navigation path used by the product.
            admin_placeholder = page.locator('[data-devpilot-feature-placeholder="admin"]')
            admin_placeholder.wait_for(state="visible", timeout=10_000)
            admin_placeholder.click()
            page.wait_for_selector(
                'script[src*="rag-admin-ui.js"]',
                state="attached",
                timeout=15_000,
            )
            page.wait_for_function(
                "() => document.querySelector('script[src*=\"rag-admin-ui.js\"]')?.dataset.devpilotFeatureLoadState === 'loaded'",
                timeout=15_000,
            )
            page.wait_for_function("() => Boolean(document.getElementById('rag-admin-view'))", timeout=15_000)

            rag_nav = page.locator('.nav[data-view="rag-admin"]')
            rag_nav.wait_for(state="visible", timeout=10_000)
            rag_nav.click()
            page.wait_for_selector("#rag-admin-view.active", timeout=10_000)
            page.wait_for_function(
                "() => document.querySelector('#rag-summary')?.textContent?.includes('RAG')",
                timeout=15_000,
            )

            # Read-only health/settings calls exercise the protected RAG API without
            # requiring embeddings, Git cloning, Redis, or an external model provider.
            api_result = page.evaluate(
                """async () => {
                  const token = localStorage.getItem('devpilot-token');
                  const headers = {Authorization: `Bearer ${token}`};
                  const [health, settings] = await Promise.all([
                    fetch('/api/super-admin/rag/health', {headers, cache: 'no-store'}),
                    fetch('/api/super-admin/rag/settings', {headers, cache: 'no-store'}),
                  ]);
                  return {
                    healthStatus: health.status,
                    settingsStatus: settings.status,
                    healthBody: await health.json(),
                    settingsBody: await settings.json(),
                  };
                }"""
            )
            assert api_result["healthStatus"] == 200
            assert api_result["settingsStatus"] == 200
            assert isinstance(api_result["healthBody"], dict)
            assert isinstance(api_result["settingsBody"], dict)

            assert not page_errors, f"JavaScript errors during RAG flow: {page_errors}"
            assert not server_errors, f"HTTP 5xx during RAG flow: {server_errors}"
        except Exception:
            page.screenshot(path=str(artifact_dir / "rag-browser-e2e-failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()
