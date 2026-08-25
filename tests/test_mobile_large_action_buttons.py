from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIONS_JS = ROOT / "app" / "static" / "mobile-action-buttons.js"
ACTIONS_CSS = ROOT / "app" / "static" / "mobile-action-buttons.css"
RESPONSES_JS = ROOT / "app" / "static" / "response-manager.js"


def test_mobile_large_actions_are_limited_to_one_third_of_viewport():
    css = ACTIONS_CSS.read_text(encoding="utf-8")

    assert "width: clamp(112px, 33.333vw, 156px)" in css
    assert "width: min(33.333vw, 132px)" in css
    assert "min-height: 58px" in css
    assert "min-height: 56px" in css
    assert "touch-action: manipulation" in css


def test_mobile_action_controller_targets_content_actions_not_bottom_navigation():
    js = ACTIONS_JS.read_text(encoding="utf-8")

    assert ".view .section-head > .primary" in js
    assert ".view .hero-actions > .primary" in js
    assert ".view [data-project-builder-open]" in js
    assert ".view .reports-actions > button" in js
    assert "mobile-simple-item" not in js
    assert "button.classList.add('dp-mobile-action')" in js


def test_mobile_actions_load_their_styles_once():
    js = ACTIONS_JS.read_text(encoding="utf-8")

    assert "link[data-mobile-action-buttons=\"1\"]" in js
    assert "/assets/mobile-action-buttons.css?v=20260825-1" in js
    assert "stylesheet.dataset.mobileActionButtons = '1'" in js


def test_immediate_large_actions_use_central_response_manager():
    js = ACTIONS_JS.read_text(encoding="utf-8")

    assert "window.DevPilotResponses?.info" in js
    assert "Abrindo ${label}…" in js
    assert "if (button.type === 'submit') return" in js


def test_submit_actions_show_pending_state_and_timeout_warning():
    js = RESPONSES_JS.read_text(encoding="utf-8")
    css = ACTIONS_CSS.read_text(encoding="utf-8")

    assert "markPendingAction(event.submitter)" in js
    assert "button.classList.add('dp-action-pending')" in js
    assert "button.setAttribute('aria-busy', 'true')" in js
    assert "loading(message, {timeout: 10000})" in js
    assert "options.timeout || 10000" in js
    assert "A operação está demorando mais que o esperado" in js
    assert ".dp-mobile-action.dp-action-pending" in css
    assert "dp-mobile-action-spin" in css


def test_response_manager_clears_pending_state_on_final_feedback():
    js = RESPONSES_JS.read_text(encoding="utf-8")

    assert "function clearPendingActions()" in js
    assert "if (type !== 'loading')" in js
    assert "clearPendingActions();" in js
    assert "devpilot:response" in js


def test_response_manager_boots_mobile_action_controller():
    js = RESPONSES_JS.read_text(encoding="utf-8")

    assert "script[data-mobile-action-buttons=\"1\"]" in js
    assert "/assets/mobile-action-buttons.js?v=20260825-1" in js
    assert "actions.dataset.mobileActionButtons = '1'" in js
