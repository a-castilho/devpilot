from __future__ import annotations

from app.services import alternating_flow
from app.services.recovery import AutoRecoveryService, RecoveryDecision

_QUOTA_SIGNALS = (
    "you have no credits remaining",
    "credit_balance_exhausted",
    "insufficient_quota",
    "billing_hard_limit_reached",
    "add credits to continue using the api",
)

_ORIGINAL_EXECUTE_TASK = alternating_flow.execute_task
_ORIGINAL_CLASSIFY = AutoRecoveryService.classify
_ORIGINAL_RECOVER = AutoRecoveryService.recover


def _contains_quota_error(value: object) -> bool:
    text = str(value or "").casefold()
    return any(signal in text for signal in _QUOTA_SIGNALS)


def _execute_task(project, task):
    result = _ORIGINAL_EXECUTE_TASK(project, task)
    if not isinstance(result, dict):
        return result

    combined = "\n".join(
        str(result.get(key) or "") for key in ("stderr", "stdout", "summary", "client_report")
    )
    if not _contains_quota_error(combined):
        return result

    guarded = dict(result)
    guarded["stderr"] = (
        "OPENAI_CREDIT_BALANCE_EXHAUSTED: a credencial foi aceita pela OpenAI, "
        "mas a organização/projeto associado a esta chave está sem créditos disponíveis."
    )
    guarded["provider_blocker"] = {
        "provider": "openai",
        "category": "ai_quota",
        "retryable": False,
        "external_condition": True,
    }
    return guarded


def _classify(self: AutoRecoveryService, error_text: str) -> str:
    if _contains_quota_error(error_text) or "openai_credit_balance_exhausted" in str(error_text or "").casefold():
        return "ai_quota"
    return _ORIGINAL_CLASSIFY(self, error_text)


def _recover(self: AutoRecoveryService, project, task, error_text: str, execution_attempt: int) -> RecoveryDecision:
    if self.classify(error_text) == "ai_quota":
        return RecoveryDecision(
            category="ai_quota",
            status="needs_authorization",
            message=(
                "A OpenAI aceitou a credencial, mas a organização/projeto associado à chave está sem créditos. "
                "O DevPilot interrompeu novas tentativas para não manter a fila ocupada inutilmente."
            ),
            retry=False,
            requires_authorization=True,
            strategy="wait_for_openai_billing",
            steps=[{
                "state": "detected",
                "attempt": execution_attempt,
                "category": "ai_quota",
                "message": "OpenAI API sem créditos disponíveis para esta credencial.",
            }],
        )
    return _ORIGINAL_RECOVER(self, project, task, error_text, execution_attempt)


def install() -> None:
    if getattr(alternating_flow.execute_task, "_devpilot_quota_guard", False):
        return
    _execute_task._devpilot_quota_guard = True
    _classify._devpilot_quota_guard = True
    _recover._devpilot_quota_guard = True
    alternating_flow.execute_task = _execute_task
    AutoRecoveryService.classify = _classify
    AutoRecoveryService.recover = _recover


install()
