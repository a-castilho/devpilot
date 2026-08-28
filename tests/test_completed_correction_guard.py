from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_completed_action_does_not_offer_another_correction():
    ui = read("app/static/consolidated-ui.js")

    assert "function isAnalysisActionTask(task)" in ui
    assert "if (!successful || !isAnalysisTask(task) || !task?.project_id)" in ui
    assert "card.hidden = true" in ui
    assert "if (eyebrow && isAnalysisTask(task))" in ui


def test_existing_correction_is_locked_when_analysis_is_reopened():
    ui = read("app/static/consolidated-ui.js")

    assert "async function syncCorrectionAvailability(card, data, task)" in ui
    assert "const existing = tasks.find(item => String(item.prompt || '').includes(marker))" in ui
    assert "if (existing) lockCorrection(card, existing)" in ui
    assert "Correção concluída. Não é possível gerar outra correção para esta análise." in ui
    assert "slider.classList.remove('created', 'error')" in ui


def test_creation_rechecks_task_type_before_posting():
    ui = read("app/static/consolidated-ui.js")

    assert "String(data.status || '').toLowerCase() !== 'success' || !isAnalysisTask(task)" in ui
    assert "lockCorrection(card, existing)" in ui
    assert "await syncCorrectionAvailability(correction, data, task)" in ui
