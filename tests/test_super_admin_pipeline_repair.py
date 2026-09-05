from pathlib import Path

from fastapi import HTTPException
import pytest

from app.pipeline_repair_routes import manage_pipeline_repair
from app.security import Principal, Role

ROOT = Path(__file__).resolve().parents[1]


def principal(role: Role) -> Principal:
    return Principal(user_id="u1", workspace_id="w1", email="u1@example.com", role=role)


def test_pipeline_repair_is_super_admin_only():
    with pytest.raises(HTTPException) as error:
        manage_pipeline_repair(principal(Role.ADMIN))
    assert error.value.status_code == 403
    assert manage_pipeline_repair(principal(Role.SUPER_ADMIN)).role is Role.SUPER_ADMIN


def test_host_runner_allows_only_named_pipeline_repair_action():
    runner = (ROOT / "tools" / "devpilot_host_action_runner.py").read_text(encoding="utf-8")
    script = (ROOT / "tools" / "devpilot_pipeline_repair.sh").read_text(encoding="utf-8")
    assert '"pipeline_repair"' in runner
    assert 'run_script("devpilot_pipeline_repair.sh")' in runner
    assert "docker compose rm -f worker" in script
    assert "POSTGRES_DNS=OK" in script
    assert "WORKER_POSTGRES=OK" in script
    assert "docker compose down" not in script


def test_super_admin_ui_exposes_repair_button_and_api():
    source = (ROOT / "app" / "static" / "super-admin-local-test.js").read_text(encoding="utf-8")
    routes = (ROOT / "app" / "pipeline_repair_routes.py").read_text(encoding="utf-8")
    local_routes = (ROOT / "app" / "local_test_routes.py").read_text(encoding="utf-8")
    assert "Reparo & Diagnóstico" in source
    assert "Executar reparo completo" in source
    assert "/admin/pipeline-repair/run" in source
    assert 'prefix="/api/admin/pipeline-repair"' in routes
    assert "require_roles(Role.SUPER_ADMIN)" in routes
    assert "router.include_router(pipeline_repair_router)" in local_routes
