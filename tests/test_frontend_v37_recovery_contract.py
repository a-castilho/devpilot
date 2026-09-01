from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_preauth_loader_never_recovers_projects_runtime():
    loader = read("acs-loader.js")
    assert "__devpilotFrontendRecoveryV37" not in loader
    assert "recoverProjectsExperience" not in loader
    assert "__devpilotLoadFeature('projects')" not in loader
    assert "project-ships.js" not in loader
    assert "mobile-project-card-compact.js" not in loader


def test_projects_runtime_is_owned_by_feature_loader():
    features = read("feature-loader.js")
    assert "projects: [" in features
    assert "'mobile-project-card-compact.js'" in features
    assert "'project-ships.js'" in features
    assert "'product-delivery-ui.js'" in features


def test_direct_projects_navigation_loads_feature_before_navigation():
    features = read("feature-loader.js")
    assert "projects:'projects'" in features
    assert "const ready = await loadFeature(feature)" in features
    assert "navigateDirect(viewName" in features
    assert "window.devpilotNavigate(viewName" in features
