from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


# Continuity layer: v81 identity + project-scoped new-round intent.
path = "app/static/game/development-continuity.js"
text = read(path)
text = text.replace("game v80", "game v81")
text = text.replace("DevelopmentContinuityV80", "DevelopmentContinuityV81")
text = text.replace("game-v80-new-round-intent", "game-v81-new-round-intent")
text = text.replace("game80-", "game81-")
text = text.replace("data-game80-", "data-game81-")
text = text.replace("GameRecoveryV80", "GameRecoveryV81")
text = text.replace("GameSwitchProjectV80", "GameSwitchProjectV81")
text = text.replace("GameRecoverV80", "GameRecoverV81")
text = text.replace("GameLoadAllProjectsV80", "GameLoadAllProjectsV81")
old = """  function hasNewRoundIntent() {
    return sessionStorage.getItem(NEW_ROUND_INTENT_KEY) === '1';
  }

  function markNewRoundIntent() {
    sessionStorage.setItem(NEW_ROUND_INTENT_KEY, '1');
  }

  function clearNewRoundIntentWhenStarted(state) {
    if (state?.hasTasks) sessionStorage.removeItem(NEW_ROUND_INTENT_KEY);
  }
"""
new = """  function newRoundIntentProject() {
    return String(sessionStorage.getItem(NEW_ROUND_INTENT_KEY) || '').trim();
  }

  function markNewRoundIntent() {
    const state = engine()?.snapshot?.();
    if (state?.projectId) sessionStorage.setItem(NEW_ROUND_INTENT_KEY, String(state.projectId));
  }

  function clearNewRoundIntentWhenStarted(state) {
    if (state?.hasTasks && newRoundIntentProject() === String(state.projectId || '')) {
      sessionStorage.removeItem(NEW_ROUND_INTENT_KEY);
    }
  }
"""
if old not in text:
    raise SystemExit("new-round v80 block not found")
text = text.replace(old, new, 1)
text = text.replace(
    "    if (hasNewRoundIntent()) return;",
    "    if (newRoundIntentProject() === String(state.projectId)) return;",
    1,
)
write(path, text)

# Bootstrap and standalone document must expose the actual revision.
path = "app/static/game/game-bootstrap.js"
text = read(path)
text = text.replace("game-development-v80-20260902", "game-development-v81-20260902")
text = text.replace("window.__devpilotGameBootProfile = 'unified-v73';", "window.__devpilotGameBootProfile = 'development-v81';")
write(path, text)

path = "app/static/game/index.html"
text = read(path)
text = text.replace("game-development-v80-20260902", "game-development-v81-20260902")
text = text.replace('data-devpilot-game-version="v80"', 'data-devpilot-game-version="v81"')
text = text.replace("data-game-critical-boot-v80", "data-game-critical-boot-v81")
write(path, text)

# Browser E2E: public home is now the canonical unauthenticated first screen.
path = "tests/test_game_browser_e2e.py"
text = read(path)
old_login = """def _login(page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=20_000)
    page.locator("#auth-email").wait_for(state="visible", timeout=10_000)
    page.locator("#auth-email").fill(E2E_EMAIL)
    page.locator("#auth-password").fill(E2E_PASSWORD)
    page.locator("#auth-submit").click()
    page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)
"""
new_login = """def _login(page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=20_000)
    page.wait_for_selector("#auth-modal", timeout=10_000)
    if page.locator("#auth-email").count() == 0:
        page.locator("#public-login").wait_for(state="visible", timeout=10_000)
        page.locator("#public-login").click()
    page.locator("#auth-email").wait_for(state="visible", timeout=10_000)
    page.locator("#auth-email").fill(E2E_EMAIL)
    page.locator("#auth-password").fill(E2E_PASSWORD)
    page.locator("#auth-submit").click()
    page.wait_for_function("() => Boolean(localStorage.getItem('devpilot-token'))", timeout=15_000)
"""
if old_login not in text:
    raise SystemExit("old E2E login helper not found")
text = text.replace(old_login, new_login, 1)
text = text.replace("data-game80-project-switch", "data-game81-project-switch")
text = text.replace("game-v80-browser-e2e-failure.png", "game-v81-browser-e2e-failure.png")
write(path, text)

# Rename the continuity contract to the release being shipped and strengthen isolation checks.
old_test = Path("tests/test_game_development_continuity_v80.py")
new_test = Path("tests/test_game_development_continuity_v81.py")
if old_test.exists():
    text = old_test.read_text(encoding="utf-8")
    text = text.replace("V80", "V81").replace("v80", "v81").replace("game80", "game81").replace("data-game80", "data-game81")
    text += """


def test_new_round_intent_is_scoped_to_selected_project():
    source = Path("app/static/game/development-continuity.js").read_text(encoding="utf-8")
    assert "newRoundIntentProject() === String(state.projectId)" in source
    assert "sessionStorage.setItem(NEW_ROUND_INTENT_KEY, String(state.projectId))" in source
    assert "sessionStorage.getItem(NEW_ROUND_INTENT_KEY) === '1'" not in source
"""
    new_test.write_text(text, encoding="utf-8")
    old_test.unlink()

# v81 documentation should identify the release contract explicitly.
path = "docs/GAME_DEVELOPMENT_TOOL.md"
text = read(path)
text = text.replace("# Modo Jogo como ferramenta de desenvolvimento", "# Modo Jogo como ferramenta de desenvolvimento — v81", 1)
write(path, text)

print("GAME_V81_FOLLOWUP=OK")
