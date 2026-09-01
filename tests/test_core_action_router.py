from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_critical_actions_bypass_generic_click_replay():
    assert "function openTaskDirect(trigger)" in LOADER
    assert "function openProjectBuilderDirect(trigger)" in LOADER
    assert "function analyzeProjectDirect(trigger)" in LOADER
    assert "const taskTrigger = target.closest('[data-open=\"task-modal\"], [data-project-task]');" in LOADER
    assert "const projectBuilderTrigger = target.closest('[data-project-builder-open]');" in LOADER
    assert "const analyzeTrigger = target.closest('#projects-list .analyze[data-id]');" in LOADER

    triggers_block = LOADER.split("const TRIGGERS = [", 1)[1].split("];", 1)[0]
    assert "data-open=\"task-modal\"" not in triggers_block
    assert "data-project-builder-open" not in triggers_block
    assert ".nav[data-view=" not in triggers_block


def test_new_execution_uses_stable_core_entrypoint():
    assert "window.devpilotOpenTaskModal({projectId, source})" in LOADER
    assert "loadFeature('taskModal')" in LOADER


def test_new_project_loads_builder_without_replaying_original_click():
    assert "await loadFeature('projectBuilder')" in LOADER
    assert "failures.includes('project-builder.js')" in LOADER
    assert "groups.children.length" in LOADER
    assert "showView('new-project')" in LOADER
    assert "title.textContent = 'Novo projeto'" in LOADER
    assert "projectBuilderTrigger.dataset.devpilotFeatureReplay" not in LOADER


def test_data_view_navigation_loads_its_bundle_but_never_blocks_base_view():
    assert "const VIEW_FEATURES = Object.freeze" in LOADER
    for item in [
        "organizations:'organizations'",
        "projects:'projects'",
        "tasks:'tasks'",
        "providers:'providers'",
        "reports:'reports'",
        "audit:'audit'",
    ]:
        assert item in LOADER
    assert "const ready = await loadFeature(feature);" in LOADER
    assert "Tela aberta com alguns recursos opcionais indisponíveis." in LOADER
    assert "window.devpilotNavigate(viewName, {source, immediate:true})" in LOADER
    assert "showView(viewName);" in LOADER
    assert "Não foi possível carregar ${viewName}. Tente novamente." not in LOADER


def test_core_actions_win_capture_before_dynamic_rerenders():
    assert "document.addEventListener('click', event => {" in LOADER
    assert "event.stopImmediatePropagation();\n      openTaskDirect(taskTrigger);" in LOADER
    assert "event.stopImmediatePropagation();\n      void openProjectBuilderDirect(projectBuilderTrigger);" in LOADER
    assert "event.stopImmediatePropagation();\n      void analyzeProjectDirect(analyzeTrigger);" in LOADER


def test_feature_loader_respects_no_idle_second_wave_policy():
    assert "requestIdleCallback" not in LOADER
    assert "idleYield" not in LOADER
