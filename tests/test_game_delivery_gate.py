from pathlib import Path

from app import product_delivery_routes as delivery
from app.delivery_url_recovery import _safe_public_url


ROOT = Path(__file__).resolve().parents[1]


def test_game_mission_ui_requires_verified_url_before_completion():
    script = (ROOT / "app/static/build-game-url-bonus.js").read_text(encoding="utf-8")

    assert "CHEFE FINAL VENCIDO · ENTREGA PENDENTE" in script
    assert "A missão só será concluída quando uma URL pública real responder com sucesso." in script
    assert "missionDelivered" in script
    assert "/delivery/validate-url" in script
    assert "MISSÃO CONCLUÍDA" in script


def test_delivery_validation_route_is_registered():
    paths = {getattr(route, "path", "") for route in delivery.router.routes}

    assert "/api/projects/{project_id}/delivery/validate-url" in paths


def test_public_url_gate_accepts_only_supported_https_hosts():
    assert _safe_public_url("https://produto.vercel.app") == "https://produto.vercel.app"
    assert _safe_public_url("https://produto.onrender.com/") == "https://produto.onrender.com"
    assert _safe_public_url("http://produto.vercel.app") == ""
    assert _safe_public_url("https://example.com") == ""
    assert _safe_public_url("javascript:alert(1)") == ""
