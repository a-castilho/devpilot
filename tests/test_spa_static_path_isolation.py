import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import STATIC, _safe_static_candidate, app


def test_index_html_never_bypasses_authenticated_shell():
    assert _safe_static_candidate("index.html") is None
    assert _safe_static_candidate("./index.html") is None
    assert _safe_static_candidate("missing/../index.html") is None


def test_assets_index_html_routes_through_authenticated_shell():
    response = TestClient(app).get("/assets/index.html")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    assert "window.__devpilotBoot" in response.text
    assert '<script src="/assets/app.js' not in response.text
    assert '<script src="/assets/feature-loader.js' not in response.text


def test_static_candidate_cannot_escape_static_root():
    outside = Path(__file__).resolve()
    relative_escape = os.path.relpath(outside, STATIC)

    assert outside.is_file()
    assert relative_escape.startswith("..")
    assert (STATIC / relative_escape).resolve() == outside
    assert _safe_static_candidate(relative_escape) is None


def test_legitimate_static_asset_is_still_served_directly():
    candidate = _safe_static_candidate("auth-ui.js")

    assert candidate == (STATIC / "auth-ui.js").resolve()
    assert candidate.is_file()


def test_missing_static_path_falls_back_to_spa_shell():
    assert _safe_static_candidate("definitely-not-a-real-devpilot-asset.js") is None
