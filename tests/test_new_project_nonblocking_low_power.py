from pathlib import Path


SOURCE = Path('app/static/mobile-project-card-compact.js').read_text(encoding='utf-8')


def test_low_power_new_project_intercepts_before_core_router() -> None:
    assert "target?.closest('[data-project-builder-open]')" in SOURCE
    assert "event.stopImmediatePropagation()" in SOURCE
    assert "}, true);" in SOURCE


def test_low_power_new_project_opens_view_before_loading_bundle() -> None:
    block_start = SOURCE.index('async function openBuilderLowPower')
    block_end = SOURCE.index('\n  function loadMore()', block_start)
    block = SOURCE[block_start:block_end]

    assert block.index('showBuilderView();') < block.index("__devpilotLoadFeature('projectBuilder')")
    assert "showBuilderLoading('Carregando cadastro de projeto…');" in block
    assert "window.setTimeout(refreshBuilderOrganizations, 0);" in block


def test_builder_organizations_are_loaded_after_view_is_available() -> None:
    assert 'function refreshBuilderOrganizations()' in SOURCE
    assert 'void Promise.resolve(loadOrganizations())' in SOURCE
    assert '.then(syncBuilderOrganizations)' in SOURCE
