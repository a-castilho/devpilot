from pathlib import Path

from app.services.delivery_product_guard import _preflight_reasons


ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/services/delivery_product_guard.py").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/delivery_url_recovery.py").read_text(encoding="utf-8")
STABLE_UI = (ROOT / "app/static/game/stable-delivery-url.js").read_text(encoding="utf-8")


def test_metadata_only_repository_is_not_a_finished_product():
    reasons = _preflight_reasons(
        ["README.md", "AGENTS.md", ".devpilot/build-game.md"],
        ["render", "vercel"],
    )
    assert any("não contém aplicação executável" in reason for reason in reasons)
    assert any("Dockerfile" in reason for reason in reasons)
    assert any("frontend publicável" in reason for reason in reasons)


def test_real_fullstack_repository_passes_structural_preflight():
    reasons = _preflight_reasons(
        ["Dockerfile", "package.json", "src/main.tsx", "app/main.py"],
        ["render", "vercel"],
    )
    assert reasons == []


def test_delivery_repair_uses_original_project_scope_and_remote_proof():
    assert "REQUISITOS ORIGINAIS RECUPERADOS DO PROJETO" in GUARD
    assert "DEVPILOT_DELIVERY_REQUIRES_REMOTE_PROOF=true" in GUARD
    assert "branch padrão remoto" in GUARD
    assert 'source="delivery-recovery"' in GUARD
    assert "requires_approval=False" in GUARD
    assert "MAX_SAFE_RETRIES = 3" in GUARD


def test_product_guard_runs_before_public_url_recovery():
    cloud_pos = RECOVERY.index("install_delivery_cloud_bridge()")
    guard_pos = RECOVERY.index("install_delivery_product_guard()")
    wrapper_pos = RECOVERY.index("current = delivery.run_delivery", guard_pos)
    assert cloud_pos < guard_pos < wrapper_pos
    assert 'if status == "repairing":' in RECOVERY


def test_game_keeps_advancing_automatic_repair_until_remote_proof():
    assert "MAX_VALIDATIONS = 60" in STABLE_UI
    assert "RETRY_MS = 4000" in STABLE_UI
    assert "Corrigindo o produto final" in STABLE_UI
    assert "endpoint(projectId, '/auto')" in STABLE_UI
    assert "repair_task_status" in STABLE_UI
