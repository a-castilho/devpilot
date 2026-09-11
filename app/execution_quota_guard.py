from __future__ import annotations

import json

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ProviderCredential
from app.services import alternating_flow
from app.services import executor as executor_service
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


def _google_credential(task):
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
            return "", []
        try:
            api_key = Vault().decrypt(credential.encrypted_secret).strip()
        except ValueError:
            return "", []
        try:
            payload = json.loads(str(credential.models or "[]"))
        except (TypeError, ValueError):
            payload = []
        models = [str(item).strip() for item in payload if str(item).strip()] if isinstance(payload, list) else []
        models = [item for item in models if item.startswith("gemini-")]
        return api_key, models or ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]


def _google_text_fallback(project, task, api_key: str, models: list[str]) -> dict | None:
    if not is_read_only_task(task) and "planejamento" not in str(task.title or "").casefold():
        return None
    instruction = (
        "Você é o provedor secundário do DevPilot. Execute análise/planejamento sem alterar arquivos. "
        "Responda em português do Brasil com plano objetivo, critérios de aceite, riscos e próximo passo.\n\n"
        f"PROJETO: {project.name}\nTAREFA: {task.title}\n\nPEDIDO:\n{task.prompt}"
    )[:100_000]
    errors: list[str] = []
    with httpx.Client(timeout=45.0) as client:
        for model in models[:3]:
            try:
                response = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                    json={"contents": [{"role": "user", "parts": [{"text": instruction}]}]},
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
            if text:
                return {
                    "exit_code": 0,
                    "mode": "analysis-read-only",
                    "summary": "Fallback concluído com Google Gemini.",
                    "client_report": text,
                    "stdout": text,
                    "stderr": "",
                    "provider_failover": {"primary": "openai", "selected": "google", "model": model, "reason": "openai_ai_quota"},
                }
    return None


def _google_agent_fallback(project, task, previous: dict, api_key: str, models: list[str]) -> dict | None:
    if is_read_only_task(task):
        return None
    repository = executor_service.ensure_repository(project)
    branch = str(previous.get("branch") or task.branch_name or f"devpilot/{task.id[:8]}").strip()
    current = executor_service.run(["git", "branch", "--show-current"], cwd=repository)
    current_branch = current.stdout.strip() if current.returncode == 0 else ""
    if current_branch != branch:
        switched = executor_service.run(["git", "switch", branch], cwd=repository)
        if switched.returncode:
            switched = executor_service.run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=repository)
        if switched.returncode:
            return None

    prompt = (
        executor_service.development_prompt(task)
        + "\n\nPROVIDER FAILOVER: OpenAI/Codex ficou indisponível. Você é o executor secundário autorizado. "
          "Pode criar, editar, renomear e excluir arquivos necessários nesta branch e executar testes locais. "
          "Não faça push, merge, deploy nem altere credenciais. Preserve a menor alteração correta e segura."
    )[:100_000]

    for model in models[:3]:
        command = [
            "gemini", "--model", model, "--prompt", prompt,
            "--approval-mode", "yolo", "--skip-trust", "--output-format", "text",
        ]
        result = executor_service.run(
            command,
            cwd=repository,
            timeout=executor_service.task_timeout(project),
            env_overrides={"GEMINI_API_KEY": api_key, "GOOGLE_API_KEY": api_key},
        )
        if result.returncode == 0:
            return {
                "exit_code": 0,
                "mode": "execute",
                "summary": "Execução concluída com Google Gemini após failover da OpenAI.",
                "client_report": result.stdout[-30_000:],
                "stdout": result.stdout[-100_000:],
                "stderr": result.stderr[-20_000:],
                "branch": branch,
                "provider_failover": {"primary": "openai", "selected": "google", "model": model, "reason": "openai_ai_quota", "write_enabled": True},
            }
    return None


def _execute_task(project, task):
    result = _ORIGINAL_EXECUTE_TASK(project, task)
    if not isinstance(result, dict):
        return result
    combined = "\n".join(str(result.get(key) or "") for key in ("stderr", "stdout", "summary", "client_report"))
    if not _contains_quota_error(combined):
        return result

    api_key, models = _google_credential(task)
    fallback = None
    if api_key:
        fallback = _google_text_fallback(project, task, api_key, models)
        if fallback is None:
            fallback = _google_agent_fallback(project, task, result, api_key, models)
    if isinstance(fallback, dict) and fallback.get("exit_code", 1) == 0:
        return fallback

    guarded = dict(result)
    guarded["stderr"] = "OPENAI_CREDIT_BALANCE_EXHAUSTED: OpenAI sem créditos e nenhum executor secundário concluiu a tarefa."
    guarded["provider_blocker"] = {
        "provider": "openai",
        "category": "ai_quota",
        "retryable": False,
        "external_condition": True,
        "fallback_attempted": bool(api_key),
        "fallback_provider": "google" if api_key else None,
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
            message="OpenAI está sem créditos e o failover Google também não concluiu esta tarefa.",
            retry=False,
            requires_authorization=True,
            strategy="multi_provider_failover_then_stop",
            steps=[{"state": "detected", "attempt": execution_attempt, "category": "ai_quota", "message": "OpenAI sem créditos; Google Gemini foi tentado como executor secundário."}],
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
