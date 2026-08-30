from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_JS = ROOT / "app" / "static" / "project-description-profile.js"
PROVISIONING_ROUTES = ROOT / "app" / "project_provisioning_routes.py"
API_ROUTES = ROOT / "app" / "api.py"


def test_project_builder_offers_independent_ship_as_default_path():
    source = PROFILE_JS.read_text(encoding="utf-8")

    assert 'value="deferred" checked' in source
    assert "Criar nave independente" in source
    assert "organization_id: null" in source
    assert "project_blueprint: {}" in source
    assert "configuration_status: 'pending'" in source
    assert "affiliation_status: 'independent'" in source
    assert "api('/projects/deferred'" in source


def test_deferred_project_backend_accepts_no_organization():
    source = PROVISIONING_ROUTES.read_text(encoding="utf-8")

    assert "organization_id: str | None = None" in source
    assert '@router.post("/projects/deferred", status_code=201)' in source
    assert "organization = optional_organization(db, ws.id, payload.organization_id)" in source


def test_project_can_be_affiliated_to_an_organization_later():
    source = API_ROUTES.read_text(encoding="utf-8")

    assert '@router.patch("/projects/{project_id}")' in source
    assert 'if values.get("organization_id"):' in source
    assert 'organization_or_404(db, ws.id, values["organization_id"])' in source
