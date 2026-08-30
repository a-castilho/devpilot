import importlib.util
import os
import subprocess
import urllib.error
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def load_terminal_helper():
    path = ROOT / "tools/devpilot_terminal_capture.py"
    spec = importlib.util.spec_from_file_location("devpilot_terminal_capture_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_shipped_terminal_activation_sequence_installs_hook(tmp_path):
    html = read("app/static/telemetry.html")
    expected = (
        "export DEVPILOT_URL=http://127.0.0.1:8080\n"
        "export DEVPILOT_TERMINAL_CAPTURE=1\n"
        "export DEVPILOT_TELEMETRY_TOKEN='seu-token-de-acesso'\n"
        'source "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh"'
    )
    assert expected in html

    command = expected.replace(
        '$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh',
        str(ROOT / "tools/devpilot_terminal_capture.sh"),
    )
    result = subprocess.run(
        ["bash", "-c", f"{command}\nprintf '%s' \"${{_DEVPILOT_CAPTURE_HOOK_INSTALLED:-}}\""],
        cwd=ROOT,
        env={**os.environ, "HOME": str(tmp_path)},
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout == "1"


@pytest.mark.parametrize("status", [401, 403])
def test_auth_breaker_survives_helper_invocations(monkeypatch, tmp_path, status):
    helper = load_terminal_helper()
    breaker = tmp_path / "telemetry-breaker.json"
    calls = []

    def reject(request, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "auth", {}, None)

    monkeypatch.setattr(helper.urllib.request, "urlopen", reject)
    monkeypatch.setenv("DEVPILOT_TERMINAL_CAPTURE", "1")
    monkeypatch.setenv("DEVPILOT_TELEMETRY_TOKEN", "expired-token")
    monkeypatch.setenv("DEVPILOT_CAPTURE_COMMAND", "echo hello")
    monkeypatch.setenv("DEVPILOT_TELEMETRY_BREAKER_FILE", str(breaker))

    assert helper.main() == 0
    assert breaker.exists()
    assert helper.main() == 0
    assert len(calls) == 1
    assert "expired-token" not in breaker.read_text(encoding="utf-8")

    monkeypatch.setenv("DEVPILOT_TELEMETRY_TOKEN", "replacement-token")
    assert helper.main() == 0
    assert len(calls) == 2


def test_terminal_capture_stops_on_auth_failures_without_fallback_churn():
    helper = read("tools/devpilot_terminal_capture.py")

    assert "{401, 403}" in helper
    assert "auth_breaker_open" in helper
    assert "open_auth_breaker" in helper
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
