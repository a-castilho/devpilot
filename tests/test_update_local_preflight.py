from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/update-local-preflight.sh"


def test_preflight_uses_nonexistent_child_path_for_git_worktree():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'TMP_PARENT="$(mktemp -d ' in source
    assert 'TMP="$TMP_PARENT/worktree"' in source
    assert 'git worktree add --quiet --detach "$TMP" "$TARGET_SHA" || fail' in source
    assert 'rm -rf "$TMP_PARENT"' in source


def test_preflight_reports_validation_failures_instead_of_silent_set_e_exit():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'run_limited node --check app/static/feature-loader.js || fail' in source
    assert 'run_limited "$PYTHON" -m pytest -q tests/test_post_login_game_lazy_boot.py' in source
    assert '|| fail "regressão detectada no boot lazy do jogo."' in source
    assert 'git merge --ff-only "$TARGET" || fail' in source
