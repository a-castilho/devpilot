from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_direct_project_builder_keeps_regular_user_in_automatic_mode():
    block = FEATURE_LOADER.split("async function openProjectBuilderDirect", 1)[1].split(
        "async function analyzeProjectDirect", 1
    )[0]
    regular = block.split("if (!admin)", 1)[1].split("hydrateBuilderOrganizations", 1)[0]

    assert "createRadio.disabled = false" in regular
    assert "createRadio.checked = true" in regular
    assert "connectRadio.checked = false" in regular
    assert "createRadio.disabled = true" not in regular
    assert "connectRadio.checked = true" not in regular
