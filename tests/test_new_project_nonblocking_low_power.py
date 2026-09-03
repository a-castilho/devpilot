from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = (ROOT / 'app/static/mobile-project-card-compact.js').read_text(encoding='utf-8')
LOADER = (ROOT / 'app/static/feature-loader.js').read_text(encoding='utf-8')
VIEWPORT = (ROOT / 'app/static/viewport-adaptive-v15.js').read_text(encoding='utf-8')


def test_low_power_runtime_does_not_own_new_project_navigation() -> None:
    assert "[data-project-builder-open]" not in MOBILE
    assert "[data-project-builder-open]" not in VIEWPORT


def test_canonical_new_project_opens_view_before_loading_bundle() -> None:
    block_start = LOADER.index('async function openProjectBuilderDirect')
    block_end = LOADER.index('\n  async function analyzeProjectDirect', block_start)
    block = LOADER[block_start:block_end]

    assert block.index('showProjectBuilderImmediately();') < block.index("await loadFeature('projectBuilder')")
    assert "trigger.dataset.devpilotOpening = '1';" in block
    assert "trigger.removeAttribute('aria-busy');" in block


def test_builder_organizations_are_loaded_without_blocking_view() -> None:
    block_start = LOADER.index('async function openProjectBuilderDirect')
    block_end = LOADER.index('\n  async function analyzeProjectDirect', block_start)
    block = LOADER[block_start:block_end]

    assert 'organizationsPromise = Promise.resolve(loadOrganizations())' in block
    assert "await loadFeature('projectBuilder')" in block
    assert 'void organizationsPromise.then(() => hydrateBuilderOrganizations(admin));' in block
