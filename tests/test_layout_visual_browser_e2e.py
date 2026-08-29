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
    page.wait_for_selector(".sidebar", state="visible", timeout=10_000)


def _artifact_dir() -> Path:
    path = Path(os.getenv("DEVPILOT_TEST_RESULTS_DIR", ".artifacts/test-results")) / "visual"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_layout_visual_desktop_and_mobile(e2e_server):
    playwright_api = pytest.importorskip("playwright.sync_api")
    artifacts = _artifact_dir()

    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])

        desktop = browser.new_context(viewport={"width": 1440, "height": 900})
        desktop_page = desktop.new_page()
        try:
            _login(desktop_page, e2e_server)

            desktop_page.screenshot(path=str(artifacts / "layout-desktop-expanded.png"), full_page=True)

            expanded = desktop_page.evaluate(
                """() => {
                  const sidebar = document.querySelector('.sidebar');
                  const main = document.querySelector('main, .main, .content');
                  const toggle = document.querySelector('.sidebar-collapse-toggle');
                  const box = sidebar.getBoundingClientRect();
                  return {
                    sidebarWidth: box.width,
                    toggleVisible: !!toggle && getComputedStyle(toggle).display !== 'none',
                    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    mainWidth: main ? main.getBoundingClientRect().width : 0,
                  };
                }"""
            )
            assert expanded["toggleVisible"], "desktop sidebar collapse control must be visible"
            assert expanded["sidebarWidth"] >= 180, f"expanded sidebar unexpectedly narrow: {expanded['sidebarWidth']}"
            assert expanded["overflowX"] <= 1, f"desktop horizontal overflow: {expanded['overflowX']}"

            desktop_page.locator(".sidebar-collapse-toggle").click()
            desktop_page.wait_for_function(
                "() => document.documentElement.classList.contains('sidebar-collapsed')",
                timeout=5_000,
            )
            desktop_page.screenshot(path=str(artifacts / "layout-desktop-collapsed.png"), full_page=True)

            collapsed = desktop_page.evaluate(
                """() => {
                  const sidebar = document.querySelector('.sidebar');
                  const main = document.querySelector('main, .main, .content');
                  return {
                    sidebarWidth: sidebar.getBoundingClientRect().width,
                    mainWidth: main ? main.getBoundingClientRect().width : 0,
                    persisted: localStorage.getItem('devpilot-sidebar-collapsed'),
                  };
                }"""
            )
            assert collapsed["sidebarWidth"] < expanded["sidebarWidth"] - 80
            assert collapsed["persisted"] == "true"
            if expanded["mainWidth"] and collapsed["mainWidth"]:
                assert collapsed["mainWidth"] > expanded["mainWidth"]
        finally:
            desktop.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        mobile_page = mobile.new_page()
        try:
            _login(mobile_page, e2e_server)
            mobile_page.screenshot(path=str(artifacts / "layout-mobile-390x844.png"), full_page=True)

            mobile_state = mobile_page.evaluate(
                """() => {
                  const toggle = document.querySelector('.sidebar-collapse-toggle');
                  const cards = [...document.querySelectorAll('.metrics > *')].filter(el => {
                    const style = getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                  });
                  const rects = cards.map(el => el.getBoundingClientRect());
                  const onePerRow = rects.length < 2 || rects.every((rect, index) => {
                    if (index === 0) return true;
                    return Math.abs(rect.left - rects[0].left) <= 2 && rect.top > rects[index - 1].top;
                  });
                  return {
                    toggleHidden: !toggle || getComputedStyle(toggle).display === 'none',
                    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    metricCount: rects.length,
                    onePerRow,
                  };
                }"""
            )
            assert mobile_state["toggleHidden"], "desktop collapse control must stay hidden on mobile"
            assert mobile_state["overflowX"] <= 1, f"mobile horizontal overflow: {mobile_state['overflowX']}"
            assert mobile_state["onePerRow"], "mobile metrics must render one card per row"
        finally:
            mobile.close()
            browser.close()
