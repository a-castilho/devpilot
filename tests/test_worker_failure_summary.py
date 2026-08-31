from types import SimpleNamespace

from app.worker import _preserve_executor_failure


def _decision(message: str = "A falha ainda não possui uma estratégia automática segura cadastrada."):
    return SimpleNamespace(
        message=message,
        steps=[{"state": "detected", "message": "erro real detectado"}],
    )


def test_preserves_executor_specific_summary_instead_of_generic_recovery_message() -> None:
    result = {"summary": "Falhou ao executar npm run build", "stderr": "vite: build failed"}

    _preserve_executor_failure(result, _decision(), "vite: build failed")

    assert result["summary"] == "Falhou ao executar npm run build"
    assert result["recovery_message"] == "A falha ainda não possui uma estratégia automática segura cadastrada."


def test_uses_sanitized_detected_failure_when_executor_has_no_summary() -> None:
    result = {"summary": "", "stderr": "raw error"}

    _preserve_executor_failure(result, _decision(), "raw error")

    assert result["summary"] == "erro real detectado"
    assert result["recovery_message"]
