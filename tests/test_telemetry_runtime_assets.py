from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_terminal_capture_uses_current_local_runtime_and_scoped_token():
    helper = read("tools/devpilot_terminal_capture.py")
    hook = read("tools/devpilot_terminal_capture.sh")

    assert "http://127.0.0.1:8080" in helper
    assert "resolve_token" in helper
    assert "DEVPILOT_TELEMETRY_TOKEN" in helper
    assert "DEVPILOT_BOOTSTRAP_TOKEN" not in helper
    assert 'DEVPILOT_URL:=http://127.0.0.1:8080' in hook


def test_terminal_capture_is_opt_in_and_requires_explicit_token():
    helper = read("tools/devpilot_terminal_capture.py")
    hook = read("tools/devpilot_terminal_capture.sh")
    installer = read("scripts/instalar-aliases-linux.sh")

    assert 'os.getenv("DEVPILOT_TERMINAL_CAPTURE", "0").strip() != "1"' in helper
    assert '${DEVPILOT_TERMINAL_CAPTURE:-0}' in hook
    assert '${DEVPILOT_TELEMETRY_TOKEN:-}' in hook
    assert 'export DEVPILOT_TERMINAL_CAPTURE="${DEVPILOT_TERMINAL_CAPTURE:-0}"' in installer
    assert '[ "${DEVPILOT_TERMINAL_CAPTURE:-0}" = "1" ]' in installer
    assert '[ -n "${DEVPILOT_TELEMETRY_TOKEN:-}" ]' in installer


def test_terminal_capture_stops_on_auth_failures_without_fallback_churn():
    helper = read("tools/devpilot_terminal_capture.py")

    assert "{401, 403, 404, 409}" in helper
    assert 'return [configured or "http://127.0.0.1:8080"]' in helper
    assert "127.0.0.1:8081" not in helper


def test_bash_installer_does_not_enable_terminal_capture_implicitly():
    installer = read("scripts/instalar-aliases-linux.sh")

    assert "devpilot_terminal_capture.sh" in installer
    assert 'export DEVPILOT_URL="http://127.0.0.1:8080"' in installer
    assert "Telemetria de terminal: desabilitada por padrão" in installer
    assert "nunca reutilize DEVPILOT_BOOTSTRAP_TOKEN" in installer


def test_browser_capture_persists_pending_events_across_navigation():
    capture = read("app/static/telemetry-capture.js")

    assert "devpilot-telemetry-pending-v1" in capture
    assert "localStorage.setItem(PENDING_KEY" in capture
    assert "pagehide" in capture
    assert "queue.unshift(...batch)" in capture


def test_telemetry_page_loads_retry_layer_before_app_script():
    html = read("app/static/telemetry.html")
    network = read("app/static/telemetry-network.js")

    assert "127.0.0.1:8081" not in html
    assert html.index("/assets/telemetry-network.js") < html.index("/assets/telemetry.js")
    assert "502,503,504" in network
    assert "http://127.0.0.1:8080" in network
