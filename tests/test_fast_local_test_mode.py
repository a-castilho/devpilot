from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = (ROOT / "docker-compose.test.yml").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts/devpilot-test-fast.sh").read_text(encoding="utf-8")


def test_fast_override_mounts_source_into_runtime_services():
    assert "./app:/app/app" in OVERRIDE
    for service in ("app:", "worker:", "rag-worker:"):
        assert service in OVERRIDE


def test_frontend_fast_path_has_no_rebuild_or_restart():
    assert "MODO: FRONTEND/HOT MOUNT (SEM REBUILD E SEM RESTART)" in SCRIPT
    assert '"${COMPOSE[@]}" up -d --no-build app' in SCRIPT
    assert "docker compose build --no-cache" not in SCRIPT


def test_python_path_restarts_without_rebuilding_image():
    assert "MODO: PYTHON + WORKERS (SEM REBUILD)" in SCRIPT
    assert '"${COMPOSE[@]}" restart app worker rag-worker' in SCRIPT


def test_dependency_changes_use_cached_rebuild_only():
    assert "Dockerfile|pyproject.toml|requirements*.txt" in SCRIPT
    assert '"${COMPOSE[@]}" build app worker rag-worker' in SCRIPT
    assert "--no-cache" not in SCRIPT


def test_fast_mode_proves_served_asset_matches_host_source():
    assert "sha256sum app/static/feature-loader.js" in SCRIPT
    assert "ASSET_BIND_MOUNT=OK" in SCRIPT
    assert "FAST_TEST=APROVADO" in SCRIPT
