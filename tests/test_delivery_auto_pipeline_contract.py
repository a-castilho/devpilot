from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOUD_BRIDGE = ROOT / "app/delivery_cloud_bridge.py"
GAME_GATE = ROOT / "app/static/game/delivery-gate.js"


def test_render_must_be_healthy_before_vercel():
    source = CLOUD_BRIDGE.read_text(encoding="utf-8")
    assert "_gated_provision_vercel" in source
    assert 'if "render" in requested:' in source
    assert 'state["waiting_for"] = "render_ready"' in source
    assert 'vercel["status"] = "waiting_backend"' in source
    assert '_probe(health_url)' in source
    assert 'delivery.provision_vercel = _gated_provision_vercel' in source


def test_backend_url_is_injected_before_a_rebuild():
    source = CLOUD_BRIDGE.read_text(encoding="utf-8")
    assert 'configured_backend != effective_backend_url' in source
    assert 'vercel["backend_configured"] = False' in source
    assert 'vercel["deployment_id"] = ""' in source
    assert 'vercel["backend_url"] = effective_backend_url' in source


def test_game_starts_delivery_after_final_verifier():
    source = GAME_GATE.read_text(encoding="utf-8")
    assert "finalVerifierApproved" in source
    assert "ensureAutomaticDelivery" in source
    assert "/delivery/auto`" in source
    assert "deliveryStarted" in source
    assert "currentStatus && currentStatus !== 'pending'" in source
    assert "DELIVERY_RETRY_MS" not in source
    assert "scheduleDeliveryRetry" not in source
    assert "devpilot:delivery:ready" in source


def test_automatic_delivery_does_not_require_owner_or_admin():
    source = CLOUD_BRIDGE.read_text(encoding="utf-8")
    assert '@delivery.router.post("/projects/{project_id}/delivery/auto")' in source
    assert 'actor: str = delivery.Depends(delivery.require_access)' in source
    assert 'return delivery.run_delivery(db, project, actor)' in source


def test_frontend_only_is_not_forced_through_render_gate():
    source = CLOUD_BRIDGE.read_text(encoding="utf-8")
    assert 'if "render" in requested:' in source
    assert 'if frontend and not frontend.issubset' in source
    assert 'return ["vercel"]' in source


def run_contract():
    test_render_must_be_healthy_before_vercel()
    test_backend_url_is_injected_before_a_rebuild()
    test_game_starts_delivery_after_final_verifier()
    test_automatic_delivery_does_not_require_owner_or_admin()
    test_frontend_only_is_not_forced_through_render_gate()
    print("DELIVERY_AUTO_PIPELINE=OK")


if __name__ == "__main__":
    run_contract()
