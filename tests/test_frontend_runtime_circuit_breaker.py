from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_feature_loader_is_explicit_and_has_no_global_observer():
    runtime = read("app/static/feature-loader.js")

    assert "window.__devpilotLoadFeature = loadFeature" in runtime
    assert "FEATURE_BUNDLES" in runtime
    assert "document.addEventListener('click'" in runtime
    assert "MutationObserver" not in runtime
    assert "body.appendChild =" not in runtime
    assert "document.body.appendChild(script)" in runtime


def test_feature_loader_does_no_menu_work_before_dashboard_reveal():
    runtime = read("app/static/feature-loader.js")

    assert "devpilot-auth-pending" in runtime
    assert "devpilot:dashboard-revealed" in runtime
    assert "initializePlaceholders" in runtime
    assert "initializeAuthenticatedUi" in runtime
    tail = runtime.split("let placeholdersInitialized", 1)[1]
    assert "document.addEventListener('devpilot:dashboard-revealed', initializeAuthenticatedUi" in tail
    init_block = runtime.split("function initializeAuthenticatedUi()", 1)[1].split("if (document.documentElement.classList.contains", 1)[0]
    assert "initializePlaceholders();" in init_block
    assert "initializeMobileShell();" in init_block


def test_acs_loader_never_modifies_browser_primitives():
    loader = read("app/static/acs-loader.js")

    assert "document.body.style.overflow = 'hidden'" not in loader
    assert "loader.style.pointerEvents = 'none'" in loader
    assert "devpilot:authenticated-core-ready" in loader
    assert "MutationObserver" not in loader
    assert "window.MutationObserver =" not in loader
    assert "body.appendChild =" not in loader
    assert "HTMLCollection.prototype" not in loader


def test_authenticated_backend_loader_has_no_second_wave():
    main = read("app/main.py")
    loader = main.split("def _authenticated_script_loader()", 1)[1].split("@asynccontextmanager", 1)[0]

    assert "deferredSources" not in loader
    assert "loadDeferred" not in loader
    assert "requestIdleCallback" not in loader
    assert "while (document.hidden" not in loader


def test_heavy_modules_are_not_part_of_core_boot():
    main = read("app/main.py")
    core_block = main.split("_CORE_AUTHENTICATED_SCRIPTS = [", 1)[1].split("]", 1)[0]

    assert '"token-usage.js"' not in core_block
    assert '"cloud-admin.js"' not in core_block
    assert '"linux-terminal.js"' not in core_block
    assert '"workspace-skins.js"' not in core_block
    assert '"simplified-nav.js"' not in core_block
