from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "app" / "static" / "game-shell.js"
ENTRY = ROOT / "app" / "static" / "game-entry.js"


def test_game_view_observer_only_tracks_active_class_transition():
    js = SHELL.read_text(encoding="utf-8")
    assert "viewObserver.observe(view, {attributes: true, attributeFilter: ['class']})" in js
    assert "viewObserver.observe(view, {attributes: true, attributeFilter: ['class'], childList: true, subtree: true})" not in js
    assert "record.type === 'attributes' && record.attributeName === 'class'" in js


def test_internal_game_render_cannot_reenter_shell_through_view_observer():
    js = SHELL.read_text(encoding="utf-8")
    observer_block = js[js.index("function watchView(view)"):js.index("function captureBaseLoader()")]
    assert "record.attributeName === 'class'" in observer_block
    assert "childList" not in observer_block.split("viewObserver.observe", 1)[1]
    assert "subtree" not in observer_block.split("viewObserver.observe", 1)[1]


def test_enter_is_idempotent_and_emits_entered_only_for_real_transition():
    js = SHELL.read_text(encoding="utf-8")
    enter_block = js[js.index("function enterGame"):js.index("function restoreView")]
    assert "const alreadyActive" in enter_block
    assert "if (!alreadyActive)" in enter_block
    assert "METRICS.enters += 1" in enter_block
    assert "events.emit('entered'" in enter_block


def test_exit_is_idempotent_and_does_not_repeat_exit_event():
    js = SHELL.read_text(encoding="utf-8")
    exit_block = js[js.index("function exitGame"):js.index("function sync()")]
    assert "const wasActive" in exit_block
    assert "if (wasActive)" in exit_block
    assert "METRICS.exits += 1" in exit_block


def test_game_loader_refreshes_hud_after_real_render_without_dom_storm():
    js = SHELL.read_text(encoding="utf-8")
    assert "function wrapGameLoader()" in js
    assert "loadInFlight = Promise.resolve().then(() => original(...args)).then(result => {" in js
    assert "METRICS.dedupedLoads += 1" in js
    assert "refresh();" in js
    assert "loadInFlight = null" in js
    assert "__devpilotGameStableWrapper" in js


def test_game_entry_uses_explicit_shell_handoff():
    js = ENTRY.read_text(encoding="utf-8")
    assert "window.DevPilotGameShell?.enter?.(document.getElementById('build-game-view'))" in js
    assert "requestAnimationFrame(() => window.DevPilotGameShell?.sync?.())" not in js


def test_runtime_exposes_small_diagnostic_counters_for_mobile_stress_checks():
    js = SHELL.read_text(encoding="utf-8")
    assert "window.__devpilotGameRuntime" in js
    for counter in ("enters", "exits", "refreshes", "classTransitions", "baseLoads", "dedupedLoads"):
        assert counter in js
    assert "metrics: () => ({...METRICS})" in js
