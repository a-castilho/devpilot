from pathlib import Path

from app.main import _CORE_AUTHENTICATED_SCRIPTS


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_authenticated_core_remains_minimal():
    assert _CORE_AUTHENTICATED_SCRIPTS == ["app.js", "feature-loader.js"]


def test_feature_loader_is_the_only_owner_of_optional_runtime_chain():
    source = read("feature-loader.js")
    assert "shellCommon" in source
    assert "viewport-adaptive-v15.js" in source
    assert "page-navigation-v26.js" in source
    assert "dashboard-user-v21.js" in source
    assert "executions-v18.js" in source
    assert "executions-focus-v19.js" in source
    assert "tasks-operational-ui.js" in source
    assert "tasksAnalytics" in source
    assert "#tasks-v9-indicators" in source
    assert "tasksDetails" in source


def test_core_app_does_not_inject_optional_scripts_or_prewarm_modal():
    source = read("app.js")
    assert "tasks-operational-ui.js" not in source
    assert "prewarmTaskModal" not in source
    assert "document.createElement('script')" not in source
    assert 'document.createElement("script")' not in source
    assert "tasks: 'Execuções'" in source
    assert "Nova execução" in source


def test_viewport_adaptive_never_loads_javascript():
    source = read("viewport-adaptive-v15.js")
    assert "document.createElement('script')" not in source
    assert 'document.createElement("script")' not in source
    assert "loadExecutionsV18" not in source
    assert "loadPageNavigationV26" not in source
    assert "execution-results-v28.js" not in source


def test_task_modal_has_no_hidden_runtime_loader():
    source = read("task-modal.js")
    assert "runtime-experience-v13.js" not in source
    assert "document.createElement('script')" not in source
    assert "canonicalSource" in source
    assert "source: canonicalSource" in source
    assert "aria-labelledby" in source
    assert "aria-busy" in source


def test_tasks_operational_has_no_parallel_analytics_loader():
    source = read("tasks-operational-ui.js")
    assert "document.createElement('script')" not in source
    assert "task-analytics.js?v=" not in source
    assert "Nenhuma execução encontrada" in source
    assert "Execução excluída" in source
    assert "aria-controls" in source
    assert "aria-busy" in source


def test_mobile_menu_is_event_driven_and_has_no_global_observer_or_loader():
    source = read("mobile-accordion-menu.js")
    assert "MutationObserver" not in source
    assert "runtime-experience-v13.js" not in source
    assert "response-manager.js" not in source
    assert "game-entry.js" not in source
    assert "document.createElement('script')" not in source
    assert "devpilot:view-changed" in source
    assert "devpilot:feature-ready" in source
    assert "Execuções" in source
    assert "aria-current" in source


def test_navigation_protects_against_stale_transitions_and_supports_a11y():
    source = read("page-navigation-v26.js")
    assert "navigationEpoch" in source
    assert "epoch !== navigationEpoch" in source
    assert "aria-current" in source
    assert "prefers-reduced-motion: reduce" in source
    assert "document.title" in source


def test_execution_labels_are_event_driven_without_retry_timers():
    source = read("executions-v18.js")
    assert "directOpenTaskModal" not in source
    assert "[80, 250, 700, 1400]" not in source
    assert "devpilot:tasks-rendered" in source
    assert "devpilot:page-ready" in source


def test_dashboard_does_not_poll_for_markup():
    source = read("dashboard-user-v21.js")
    assert "attempt < 40" not in source
    assert "bootstrap(attempt" not in source
    assert "devpilot:dashboard-revealed" in source
    assert "devpilot:view-changed" in source


def test_source_markup_starts_with_execution_vocabulary_and_accessibility():
    source = read("index.html")
    assert 'data-view="tasks">Execuções</button>' in source
    assert ">+ Nova execução</button>" in source
    assert '<span class="eyebrow">EXECUÇÕES</span>' in source
    assert '<h2>Execuções</h2>' in source
    assert 'placeholder="Execução ou projeto"' in source
    assert '<th>Execução</th>' in source
    assert '<span class="eyebrow">NOVA EXECUÇÃO</span>' in source
    assert 'id="task-submit" type="submit">Salvar execução</button>' in source
    assert 'id="toast" role="status" aria-live="polite"' in source


def test_legacy_execution_submit_is_inert():
    source = read("executions-submit-v29.js")
    assert "addEventListener('submit'" not in source
    assert 'addEventListener("submit"' not in source
    assert "fetch(`/api${path}`" not in source
    assert "method: 'POST'" not in source


def test_mobile_analytics_contract_is_vertical_not_carousel():
    source = read("task-analytics.css")
    marker = "DevPilot V32 · analytics mobile incorporado"
    assert marker in source
    mobile = source.split(marker, 1)[1]
    assert "grid-template-columns: minmax(0, 1fr) !important" in mobile
    assert "overflow-x: visible !important" in mobile
    assert "scroll-snap-type: none !important" in mobile
