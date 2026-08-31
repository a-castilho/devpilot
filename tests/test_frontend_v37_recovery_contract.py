from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_recovery_bootstrap_restores_projects_visual_runtime():
    loader = read("acs-loader.js")
    assert "__devpilotFrontendRecoveryV37" in loader
    assert "layout-projects-v6.css" in loader
    assert "layout-authority-v37.css" in loader
    assert "mobile-project-card-compact.js" in loader
    assert "project-ships.js" in loader


def test_recovery_uses_existing_projects_feature_before_fallback():
    loader = read("acs-loader.js")
    features = read("feature-loader.js")
    assert "window.__devpilotLoadFeature('projects')" in loader
    assert "projects: [" in features
    assert "'project-ships.js'" in features
    assert "'mobile-project-card-compact.js'" in features


def test_recovery_covers_mobile_and_direct_projects_navigation():
    loader = read("acs-loader.js")
    assert '[data-view="projects"]' in loader
    assert '[data-simple-target="projects"]' in loader
    assert "devpilot:view-changed" in loader
    assert "hashchange" in loader
