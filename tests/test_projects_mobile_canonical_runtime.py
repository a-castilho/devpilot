from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_mobile_projects_uses_canonical_bundle():
    assert "const constrainedProjectsRuntime = () => false;" in LOADER
    projects_start = LOADER.index("projects: [")
    projects_end = LOADER.index("taskModal:", projects_start)
    bundle = LOADER[projects_start:projects_end]
    assert "'project-ships.js'" in bundle
    assert "'product-delivery-ui.js'" in bundle
