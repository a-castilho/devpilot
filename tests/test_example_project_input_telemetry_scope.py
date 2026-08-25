from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "app" / "static" / "example-project.js"
REPLAY = ROOT / "app" / "static" / "telemetry-replay-capture.js"
REPETAI = ROOT / "app" / "static" / "examples" / "repeatai" / "index.html"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_example_project_is_excluded_from_global_process_telemetry():
    text = source(EXAMPLE)
    assert "view.dataset.telemetryControl = '1';" in text
    assert "Gravador de Processos global" in text


def test_example_wizard_does_not_install_global_mouse_keyboard_or_wheel_listeners():
    text = source(EXAMPLE)
    assert "window.addEventListener('mousemove', onMouseMove" not in text
    assert "window.addEventListener('keydown', onKeyDown" not in text
    assert "window.addEventListener('wheel', onWheel" not in text
    assert "wizard.addEventListener('mousemove', onMouseMove" in text
    assert "wizard.addEventListener('keydown', onKeyDown" in text
    assert "wizard.addEventListener('wheel', onWheel" in text


def test_example_wizard_capture_starts_only_after_explicit_user_action_and_stops_on_completion():
    text = source(EXAMPLE)
    assert "function startWizardCapture()" in text
    assert "function stopWizardCapture()" in text
    assert "startWizardCapture();\n          state.step = 1;" in text
    assert "state.step = 4;\n      stopWizardCapture();" in text
    assert "captureController: null" in text


def test_pointer_replay_listener_is_idle_without_active_telemetry_session():
    text = source(REPLAY)
    assert "function attachPointer()" in text
    assert "if(attached||!sessionId)return;" in text
    assert "function detachPointer()" in text
    assert "if(sessionId){attachPointer();startFlushTimer()}" in text
    assert "else{detachPointer();stopFlushTimer()}" in text
    assert "setInterval(()=>void syncSession(),1800)" not in text
    assert "document.addEventListener('pointermove',onPointerMove,{capture:true,passive:true});\n  setInterval" not in text


def test_compiled_repeatai_capture_is_user_started_and_has_detach_path():
    text = source(REPETAI)
    assert "function attach(){" in text
    assert "function detach(){" in text
    assert "attach();" in text
    assert "detach();" in text
    assert "Iniciar captura" in text
    assert "O conteúdo digitado não é armazenado" in text
