from pathlib import Path


SCRIPT = Path("app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_mobile_projects_auto_delivery_waits_for_successful_tasks_before_deploying():
    assert "/tasks?project_id=${encodeURIComponent(projectId)}&limit=40" in SCRIPT
    assert "AUTO_ACTIVE" in SCRIPT
    assert "AUTO_FAILURE" in SCRIPT
    assert "return items.some(item => ['completed','done'].includes" in SCRIPT


def test_mobile_projects_auto_delivery_advances_delivery_state_machine():
    assert "/delivery/auto" in SCRIPT
    assert "AUTO_DELIVERY_MAX_RETRIES = 3" in SCRIPT
    assert "['pending','provisioning','deploying','failed','blocked']" in SCRIPT


def test_mobile_projects_surface_validated_public_url_on_project_card():
    assert "project-public-url" in SCRIPT
    assert "🌐 ${url}" in SCRIPT
    assert "Produto publicado e URL validada." in SCRIPT
