from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "app/static/project-builder.js"
LOADER = ROOT / "app/static/feature-loader.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_simple_builder_preserves_loader_readiness_contract():
    builder = text(BUILDER)
    loader = text(LOADER)

    assert "form.dataset.simpleBuilderReady = '1'" in builder
    assert 'id="project-builder-groups" hidden' in builder
    assert 'data-simple-builder-ready="1"' in builder
    assert "!groups || !groups.children.length" in loader


def test_simple_builder_remains_isolated_from_legacy_submit_handlers():
    builder = text(BUILDER)

    assert "const form = originalForm.cloneNode(false)" in builder
    assert "originalForm.replaceWith(form)" in builder
    assert "form.addEventListener('submit'" in builder
    assert "await request('/projects'" in builder
