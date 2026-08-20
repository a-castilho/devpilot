from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_terminal_capture_uses_current_local_runtime_and_resolves_token():
    helper = read("tools/devpilot_terminal_capture.py")
    hook = read("tools/devpilot_terminal_capture.sh")

    assert "http://127.0.0.1:8080" in helper
    assert "resolve_token" in helper
    assert 'DEVPILOT_URL:=http://127.0.0.1:8080' in hook


def test_bash_installer_auto_loads_terminal_capture():
    installer = read("scripts/instalar-aliases-linux.sh")

    assert "devpilot_terminal_capture.sh" in installer
    assert 'export DEVPILOT_URL="http://127.0.0.1:8080"' in installer
    assert "source \"$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh\"" in installer


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
