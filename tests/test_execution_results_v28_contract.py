from pathlib import Path


def test_execution_results_v28_contract():
    js = Path('app/static/execution-results-v28.js').read_text(encoding='utf-8')
    viewport = Path('app/static/viewport-adaptive-v15.js').read_text(encoding='utf-8')

    assert '__devpilotExecutionResultsV28' in js
    assert '/task-runs/latest?limit=500' in js
    assert '/task-runs/${encodeURIComponent(runId)}' in js
    assert 'run?.summary' in js
    assert 'flattenLogs(run?.logs)' in js
    assert 'Resultado da execução' in js or 'RESULTADO DA EXECUÇÃO' in js
    assert "oldDecision.replaceWith(result)" in js
    assert 'task.prompt' not in js
    assert 'loadExecutionResultsV28' in viewport
    assert 'execution-results-v28.js' in viewport
