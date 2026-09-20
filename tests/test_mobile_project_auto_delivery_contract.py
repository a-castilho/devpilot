from pathlib import Path


SCRIPT = Path("app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_mobile_projects_observe_backend_owned_delivery():
    assert "/projects/${encodeURIComponent(key)}/delivery" in SCRIPT
    assert "/delivery/auto" not in SCRIPT
    assert "autoDeliveryInFlight" in SCRIPT


def test_mobile_projects_surface_validated_public_url_on_project_card():
    assert "project-public-url" in SCRIPT
    assert "🌐 ${url}" in SCRIPT
    assert "Produto publicado e URL validada." in SCRIPT
