from pathlib import Path


SUBPHASES_JS = Path("app/static/build-game-subphases.js")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
VALIDATE_CI = Path("scripts/validate-ci.sh")


def test_subphase_engine_is_loaded_after_build_game():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    assert "/assets/build-game.js?v=" in loader
    assert "/assets/build-game-subphases.js?v=" in loader
    assert loader.index("/assets/build-game.js") < loader.index("/assets/build-game-subphases.js")
    assert "data-build-game-subphases-loader" in loader


def test_real_failures_create_corrective_subphases():
    source = SUBPHASES_JS.read_text(encoding="utf-8")
    assert "[DEVPILOT_BUILD_GAME_SUBPHASE_V1]" in source
    assert "api('/task-runs/latest?limit=500')" in source
    assert "new Set(['failed', 'blocked'])" in source
    assert "createCorrection" in source
    assert "SUBFASE:" in source
    assert "TAREFA_ORIGEM:" in source
    assert "MOTIVO_DA_SUBFASE:" in source
    assert "CATEGORIA_FALHA:" in source
    assert "CODIGO_FALHA:" in source


def test_corrective_subphase_is_real_fix_task_and_preserves_security():
    source = SUBPHASES_JS.read_text(encoding="utf-8")
    assert "[DEVPILOT_MODE=fix]" in source
    assert "await api('/tasks'" in source
    assert "source: 'dashboard'" in source
    assert "requires_approval: Boolean(failure?.requires_authorization)" in source
    assert "não contorne autenticação ou autorização" in source
    assert "não introduza mock indevido" in source
    assert "Não avance para a próxima fase" in source


def test_subphases_are_visible_and_bounded():
    source = SUBPHASES_JS.read_text(encoding="utf-8")
    assert "Subfases · erros e correções" in source
    assert "Correção validada" in source
    assert "MAX_SUBPHASES = 12" in source
    assert "devpilot-build-game-subphase-created" in source
    assert "build-game-subphase-error" in source


def test_subphase_css_does_not_overflow_phase_grid():
    source = SUBPHASES_JS.read_text(encoding="utf-8")
    assert "grid-column:1/-1;width:100%;min-width:0;box-sizing:border-box;margin:4px 0 0" in source
    assert "margin:4px 0 0;padding:10px 0 0 10px" in source
    assert "margin-left:58px" not in source
    assert "overflow-wrap:anywhere" in source
    assert "#build-game-view .build-game-phase{min-width:0;box-sizing:border-box}" in source


def test_ci_checks_subphase_asset():
    source = VALIDATE_CI.read_text(encoding="utf-8")
    assert "node --check app/static/build-game-subphases.js" in source
    assert "test -f .vercel-static/assets/build-game-subphases.js" in source
