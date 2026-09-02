from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")


def test_v67_installs_nonblocking_entry_between_engine_and_bootstrap():
    engine = INDEX.index('/assets/build-game.js')
    bridge = INDEX.index('data-game-nonblocking-entry-v67')
    bootstrap = INDEX.index('/assets/game/game-bootstrap.js')
    assert engine < bridge < bootstrap
    assert 'window.__devpilotGameNonBlockingEntryV67 = true' in INDEX


def test_first_visible_shell_is_rendered_before_network_hydration():
    render = INDEX.index("renderEntryShell('Abrindo a interface agora")
    hydrate = INDEX.index('void hydrate(false);', render)
    assert render < hydrate
    assert 'data-game-entry-shell-v67="1"' in INDEX
    assert 'A página não está travada' not in INDEX
    assert 'a página não está travada' in INDEX


def test_bootstrap_first_call_does_not_wait_for_projects_or_history():
    wrapper = INDEX.index('window.loadBuildGame = (...args) =>')
    deferred = INDEX.index("return Promise.resolve({deferred: !hydrated, source: 'entry-v67'});", wrapper)
    assert wrapper < deferred
    assert 'bootstrapCallPending = false' in INDEX
    assert 'if (!hydrated) return hydrationPromise || hydrate(false);' in INDEX


def test_real_engine_still_hydrates_projects_and_history_in_background():
    assert 'await ensureProjects();' in BUILD
    assert "await api(`/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500`)" in BUILD
    assert '.then(() => baseLoad())' in INDEX
    assert "target.querySelector('#build-game-project')" in INDEX
    assert "document.dispatchEvent(new CustomEvent('devpilot:game:rendered'" in INDEX


def test_v67_has_retry_and_no_recursive_polling_loop():
    assert 'data-game-entry-retry-v67' in INDEX
    assert 'void hydrate(true);' in INDEX
    assert 'while (' not in INDEX[INDEX.index('data-game-nonblocking-entry-v67'):]
    assert 'MutationObserver' not in INDEX
