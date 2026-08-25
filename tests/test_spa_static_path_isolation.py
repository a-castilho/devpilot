from pathlib import Path

from app.main import STATIC, _safe_static_candidate


def test_index_html_never_bypasses_authenticated_shell():
    assert _safe_static_candidate("index.html") is None
    assert _safe_static_candidate("./index.html") is None
    assert _safe_static_candidate("missing/../index.html") is None


def test_static_candidate_cannot_escape_static_root():
    outside = Path(__file__).resolve()
    relative_escape = f"../tests/{outside.name}"

    assert outside.is_file()
    assert _safe_static_candidate(relative_escape) is None


def test_legitimate_static_asset_is_still_served_directly():
    candidate = _safe_static_candidate("auth-ui.js")

    assert candidate == (STATIC / "auth-ui.js").resolve()
    assert candidate.is_file()


def test_missing_static_path_falls_back_to_spa_shell():
    assert _safe_static_candidate("definitely-not-a-real-devpilot-asset.js") is None
