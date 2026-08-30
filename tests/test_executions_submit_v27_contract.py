from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/executions-submit-v27.js').read_text(encoding='utf-8')
VIEWPORT = (ROOT / 'app/static/viewport-adaptive-v15.js').read_text(encoding='utf-8')


def test_execution_submit_v27_is_canonical_and_explicit():
    assert '__devpilotExecutionsSubmitV27' in JS
    assert "form.noValidate = true" in JS
    assert "form.onsubmit = submitExecution" in JS
    assert "fetch('/api/tasks'" in JS
    assert "method: 'POST'" in JS
    assert "Execução registrada com sucesso." in JS
    assert "automaticTitle(prompt)" in JS


def test_execution_submit_v27_is_loaded_by_runtime():
    assert 'loadExecutionsSubmitV27' in VIEWPORT
    assert '/assets/executions-submit-v27.js?v=20260830-1' in VIEWPORT
