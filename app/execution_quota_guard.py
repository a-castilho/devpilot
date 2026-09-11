from __future__ import annotations

import json

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ProviderCredential
from app.services import alternating_flow
from app.services.recovery import AutoRecoveryService, RecoveryDecision
from app.services.task_flow import is_read_only_task
from app.services.vault import Vault

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


def _safe_for_text_provider(task) -> bool:
    title = str(getattr(task, "title", "") or "").casefold()
    prompt = str(getattr(task, "prompt", "") or "").casefold()
    if is_read_only_task(task):
        return True
    if "planejamento" in title or "planejamento" in prompt:
        return True
    if "análise" in title or "analise" in title:
        return True
    return False


def _google_models(credential: ProviderCredential) -> list[str]:
    try:
        payload = json.loads(str(credential.models or "[]"))
    except (TypeError, ValueError):
        payload = []
    values = [str(item).strip() for item in payload if str(item).strip()] if isinstance(payload, list) else []
    preferred = [
        model for model in values
        if model.startswith("gemini-") and ("flash" in model or "pro" in model)
    ]
    return preferred or ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


def _google_fallback(project, task) -> dict | None:
    if not _safe_for_text_provider(task):
        return None

    with SessionLocal() as db:
        credential = db.scalar(
            select(ProviderCredential)
            .where(
                ProviderCredential.workspace_id == task.workspace_id,
                ProviderCredential.provider == "google",
                ProviderCredential.enabled.is_(True),
            )
            .order_by(ProviderCredential.created_at.desc())
            .limit(1)
        )
        if credential is None:
            return None
        try:
            api_key = Vault().decrypt(credential.encrypted_secret)
        except ValueError:
            return None
        models = _google_models(credential)

    instruction = (
        "Você é o provedor secundário do DevPilot. Execute somente análise/planejamento em modo seguro, "
        "sem inventar alterações já aplicadas. Responda em português do Brasil com plano objetivo, critérios "
        "de aceite, riscos e próximo passo executável.\n\n"
        f"PROJETO: {getattr(project, 'name', '')}\n"
        f"REPOSITÓRIO: {getattr(project, 'repository_url', '')}\n"
        f"TAREFA: {getattr(task, 'title', '')}\n\n"
        f"PEDIDO:\n{getattr(task, 'prompt', '')}"
    )[:100_000]

    errors: list[str] = []
    with httpx.Client(timeout=45.0) as client:
        for model in models[:3]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                response = client.post(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    json={
                        "contents": [{"role": "user", "parts": [{"text": instruction}]}],
                        "generationConfig": {"temperature": 0.2},
                    },
                )
            except httpx.HTTPError as error:
                errors.append(f"{model}:network:{type(error).__name__}")
                continue
            if response.status_code >= 400:
                errors.append(f"{model}:http:{response.status_code}")
                continue
            try:
                payload = response.json()
                candidates = payload.get("candidates") or []
                parts = (((candidates[0] or {}).get("content") or {}).get("parts") or []) if candidates else []
                text = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
            except (ValueError, TypeError, IndexError, AttributeError):
                text = ""
            if not text:
                errors.append(f"{model}:empty")
                continue
            return {
                "exit_code": 0,
                "mode": "analysis-read-only",
                "summary": "Fallback automático concluído com Google Gemini após indisponibilidade da OpenAI.",
                "client_report": text,
                "stdout": text,
                "stderr": "",
                "provider_failover": {
                    "primary": "openai",
                    "selected": "google",
                    "model": model,
                    "reason": "openai_ai_quota",
                },
            }
    return {
        "exit_code": 1,
        "mode": "provider-failover-failed",
        "summary": "OpenAI indisponível e o fallback Google também não conseguiu responder.",
        "stderr": "GOOGLE_FALLBACK_FAILED: " + "; ".join(errors[-3:]),
        "provider_failover": {
            "primary": "openai",
            "selected": None,
            "attempted": "google",
            "reason": "openai_ai_quota",
        },
    }


def _execute_task(project, task):
    result = _ORIGINAL_EXECUTE_TASK(project, task)
    if not isinstance(result, dict):
        return result

    combined = "\n".join(
        str(result.get(key) or "") for key in ("stderr", "stdout", "summary", "client_report")
    )
    if not _contains_quota_error(combined):
        return result

    fallback = _google_fallback(project, task)
    if isinstance(fallback, dict) and fallback.get("exit_code", 1) == 0:
        return fallback

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
        "fallback_attempted": bool(fallback),
        "fallback_provider": "google" if fallback else None,
    }
    if fallback:
        guarded["provider_failover"] = fallback.get("provider_failover")
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
                "A OpenAI está sem créditos e nenhum provedor secundário seguro concluiu esta etapa. "
                "O DevPilot interrompeu novas tentativas para não manter a fila ocupada inutilmente."
            ),
            retry=False,
            requires_authorization=True,
            strategy="multi_provider_failover_then_stop",
            steps=[{
                "state": "detected",
                "attempt": execution_attempt,
                "category": "ai_quota",
                "message": "OpenAI sem créditos; fallback secundário permitido apenas para análise/planejamento seguro.",
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
