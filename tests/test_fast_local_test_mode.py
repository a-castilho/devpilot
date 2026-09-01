from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = (ROOT / "docker-compose.test.yml").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts/devpilot-test-fast.sh").read_text(encoding="utf-8")


def test_fast_override_mounts_source_into_runtime_services():
    assert "./app:/app/app" in OVERRIDE
    for service in ("app:", "worker:", "rag-worker:"):
        assert service in OVERRIDE


def test_fast_script_always_combines_base_and_override_compose():
    assert 'docker-compose.yml' in SCRIPT
    assert 'docker-compose.test.yml' in SCRIPT
    assert 'COMPOSE=(docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.test.yml")' in SCRIPT
    assert '"${COMPOSE[@]}" config >/tmp/devpilot-fast-compose.yml' in SCRIPT
    assert 'COMPOSE_FAST=OK' in SCRIPT


def test_frontend_fast_path_reuses_existing_image_without_no_build_flag():
    assert "MODO: FRONTEND/HOT MOUNT (SEM REBUILD FORÇADO E SEM RESTART)" in SCRIPT
    assert '"${COMPOSE[@]}" up -d app' in SCRIPT
    assert "--no-build" not in SCRIPT
    assert "docker compose build --no-cache" not in SCRIPT


def test_python_path_restarts_without_forced_rebuild():
    assert "MODO: PYTHON + WORKERS (SEM REBUILD FORÇADO)" in SCRIPT
    assert '"${COMPOSE[@]}" up -d app worker rag-worker' in SCRIPT
    assert '"${COMPOSE[@]}" restart app worker rag-worker' in SCRIPT


def test_dependency_changes_use_cached_rebuild_only():
    assert "Dockerfile|pyproject.toml|requirements*.txt" in SCRIPT
    assert '"${COMPOSE[@]}" build app worker rag-worker' in SCRIPT
    assert "--no-cache" not in SCRIPT


def test_fast_mode_proves_served_asset_matches_host_source():
    assert "sha256sum app/static/feature-loader.js" in SCRIPT
    assert "ASSET_BIND_MOUNT=OK" in SCRIPT
    assert "FAST_TEST=APROVADO" in SCRIPT
