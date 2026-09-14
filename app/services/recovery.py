from __future__ import annotations

import base64
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential, Task
from app.services.vault import Vault


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s\"']+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


@dataclass
class RecoveryDecision:
    category: str
    status: str
    message: str
    retry: bool = False
    requires_authorization: bool = False
    strategy: str = "none"
    steps: list[dict] = field(default_factory=list)
    hard_stop: bool = False
    continue_pipeline: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class AutoRecoveryService:
    """Safe, bounded recovery with non-blocking continuation whenever integrity permits."""

    MAX_ATTEMPTS = 3

    _GITHUB_AUTH = (
        "write access to repository not granted", "requested url returned error: 401",
        "requested url returned error: 403", "authentication failed", "could not read username",
        "repository not found", "permission denied (publickey)",
    )
    _NETWORK = (
        "could not resolve host", "failed to connect", "connection timed out", "connection reset",
        "network is unreachable", "temporary failure in name resolution", "remote end hung up unexpectedly",
        "tls connection was non-properly terminated",
    )
    _REPOSITORY_STATE = ("already exists and is not an empty directory", "not a git repository", "index.lock", "shallow.lock")
    _CODEX_AUTH = ("not logged in", "unauthorized", "invalid api key", "codex login", "401 unauthorized")
    _FILESYSTEM = ("operation not permitted", "permission denied", "read-only file system")
    _DATABASE = ("connection refused", "could not connect to server", "database is unavailable", "sqlalchemy.exc.operationalerror")
    _SAFETY_INTEGRITY = (
        "database disk image is malformed",
        "data corruption detected",
        "data corruption risk",
        "irreversible data loss",
        "would destroy data",
        "destructive operation is irreversible",
        "secret exposure detected",
        "credential exposure detected",
    )

    def classify(self, error_text: str) -> str:
        text = str(error_text or "").casefold()
        if any(pattern in text for pattern in self._SAFETY_INTEGRITY): return "safety_integrity"
        if any(pattern in text for pattern in self._GITHUB_AUTH): return "github_auth"
        if any(pattern in text for pattern in self._NETWORK): return "git_network"
        if any(pattern in text for pattern in self._REPOSITORY_STATE): return "repository_state"
        if any(pattern in text for pattern in self._CODEX_AUTH): return "codex_auth"
        if any(pattern in text for pattern in self._DATABASE): return "database"
        if any(pattern in text for pattern in self._FILESYSTEM): return "filesystem_permission"
        return "unknown"

    def recover(self, project: Project | None, task: Task | None, error_text: str, execution_attempt: int) -> RecoveryDecision:
        category = self.classify(error_text)
        detected = {"state": "detected", "attempt": execution_attempt, "category": category, "message": self._safe_error(error_text)}
        if category == "safety_integrity":
            return RecoveryDecision(
                category="safety_integrity",
                status="hard_stop",
                message="A execução encontrou evidência explícita de risco à integridade ou segurança. A esteira foi interrompida somente para evitar perda/corrupção de dados, exposição de segredo ou ação destrutiva irreversível.",
                retry=False,
                requires_authorization=False,
                strategy="protect_integrity",
                steps=[detected],
                hard_stop=True,
                continue_pipeline=False,
            )
        if category == "github_auth":
            if project is None:
                return RecoveryDecision(category, "needs_attention", "Acesso GitHub indisponível; o DevPilot seguirá de forma degradada e manterá a recuperação automática em acompanhamento.", False, False, "defer_github_access", [detected])
            decision = self._recover_github_access(project, execution_attempt); decision.steps.insert(0, detected); return decision
        if category == "git_network" and execution_attempt < self.MAX_ATTEMPTS:
            delay = min(2, max(1, execution_attempt)); time.sleep(delay)
            return RecoveryDecision(category, "retrying", "Falha transitória de rede detectada. O DevPilot tentará novamente automaticamente.", True, False, "bounded_retry", [detected, {"state":"repairing","attempt":execution_attempt,"message":f"Nova tentativa agendada após {delay}s."}])
        if category == "git_network":
            return RecoveryDecision(category, "needs_attention", "A conectividade permaneceu indisponível após as tentativas controladas. O diagnóstico será mantido e a esteira poderá seguir de forma degradada.", False, False, "defer_network_failure", [detected])
        if category == "repository_state":
            repaired = self._quarantine_invalid_repository(project) if project is not None else False
            return RecoveryDecision(category, "resolved" if repaired else "needs_attention", "Área local inconsistente isolada com segurança. O DevPilot retomará a tarefa." if repaired else "O checkout local permanece inconsistente. O DevPilot registrará a pendência e continuará somente com etapas independentes.", repaired and execution_attempt < self.MAX_ATTEMPTS, False, "quarantine_invalid_checkout" if repaired else "defer_repository_repair", [detected])
        if category == "codex_auth":
            return RecoveryDecision(category, "needs_authorization", "O Codex não está autenticado no ambiente desta tentativa. A pendência será informada sem bloquear etapas independentes da esteira.", False, True, "defer_codex_authorization", [detected])
        if category == "filesystem_permission":
            return RecoveryDecision(category, "needs_authorization", "Uma permissão do sistema operacional impediu esta ação. O DevPilot preservará a evidência e seguirá com o que não depender dessa permissão.", False, True, "defer_filesystem_authorization", [detected])
        if category == "database":
            return RecoveryDecision(category, "needs_attention", "O banco está indisponível nesta tentativa, sem evidência de corrupção. O DevPilot registrará o diagnóstico e permitirá continuação degradada de etapas independentes.", False, False, "defer_database_unavailability", [detected])
        if execution_attempt < self.MAX_ATTEMPTS:
            delay = min(2, max(1, execution_attempt))
            time.sleep(delay)
            return RecoveryDecision(
                category="unknown",
                status="retrying",
                message="A causa ainda não foi classificada, mas não há evidência de risco destrutivo. O DevPilot fará uma nova tentativa controlada.",
                retry=True,
                requires_authorization=False,
                strategy="bounded_unknown_retry",
                steps=[
                    detected,
                    {
                        "state": "repairing",
                        "attempt": execution_attempt,
                        "message": f"Nova tentativa controlada agendada após {delay}s para confirmar se a falha é transitória.",
                    },
                ],
            )
        return RecoveryDecision(
            category="unknown", status="diagnosis_required",
            message="Não foi possível identificar automaticamente a causa após as tentativas controladas. O erro foi preservado para recuperação por IA e a esteira poderá continuar de forma degradada quando não houver risco explícito.",
            retry=False, requires_authorization=False, strategy="defer_ai_diagnosis", steps=[detected],
        )

    def should_continue_pipeline(self, decision: RecoveryDecision) -> bool:
        """Allow exhausted non-destructive failures to become an auditable degraded continuation."""
        if decision.hard_stop or decision.retry:
            return False
        if decision.status in {"resolved", "retrying", "hard_stop"}:
            return False
        return True

    def degraded_result(self, decision: RecoveryDecision, original_error: str, existing_result: dict | None = None) -> dict:
        """Materialize a non-blocking result without pretending the technical work fully succeeded."""
        diagnostic = self._safe_error(original_error)
        result = dict(existing_result or {})
        decision.continue_pipeline = True
        result.update(
            {
                "mode": "self-healing-degraded",
                "exit_code": 0,
                "degraded": True,
                "summary": f"Continuação degradada: a etapa não foi concluída integralmente. {decision.message}",
                "client_report": (
                    "Resumo para o cliente\n"
                    "A etapa não foi concluída integralmente nesta tentativa. O DevPilot esgotou as alternativas automáticas seguras disponíveis, registrou o diagnóstico e seguirá com as partes da esteira que não dependem desta condição.\n\n"
                    "O que encontramos\n"
                    f"Categoria identificada: {decision.category}.\n"
                    f"Diagnóstico técnico: {diagnostic}\n\n"
                    "Impacto\n"
                    "A pendência permanece registrada e não é tratada como entrega técnica concluída. Ela não bloqueará etapas independentes.\n\n"
                    "Próximo passo\n"
                    "O DevPilot manterá uma recuperação automática por IA em acompanhamento e registrará a solução ou a limitação encontrada."
                ),
                "stderr": diagnostic,
                "self_healing": {
                    "status": "deferred",
                    "category": decision.category,
                    "requires_authorization": decision.requires_authorization,
                    "strategy": decision.strategy,
                    "message": decision.message,
                    "steps": decision.steps,
                    "hard_stop": False,
                    "pipeline_continued": True,
                },
            }
        )
        return result

    def failure_result(self, decision: RecoveryDecision, original_error: str) -> dict:
        diagnostic = self._safe_error(original_error)
        if decision.hard_stop:
            summary = f"Parada de segurança: {decision.message}"
            next_step = "Preserve o estado atual e corrija a condição de integridade/segurança antes de retomar esta operação."
            impact = "A esteira foi interrompida porque continuar poderia causar dano irreversível ou exposição de dados sensíveis."
        elif decision.requires_authorization:
            summary = f"Intervenção autorizada necessária: {decision.message}"
            next_step = "A autorização foi registrada como pendência; etapas independentes podem ser tratadas pela política de continuação degradada."
            impact = "Esta ação específica depende de autorização ou permissão, mas isso não constitui automaticamente um hard stop da esteira."
        elif decision.category == "github_auth":
            summary = f"Configuração administrativa necessária: {decision.message}"
            next_step = "O DevPilot deve continuar tentando as credenciais GitHub administradas e registrar a pendência se o acesso continuar indisponível."
            impact = "A ação dependente de GitHub não foi concluída nesta tentativa."
        elif decision.category == "unknown":
            summary = f"Diagnóstico necessário: {decision.message}"
            next_step = "Preserve o erro para a recuperação por IA e continue apenas com etapas independentes quando seguro."
            impact = "A causa ainda não foi classificada, sem evidência atual de risco destrutivo."
        else:
            summary = f"Atenção necessária: {decision.message}"
            next_step = "Registre a pendência e aplique a política de continuação degradada quando não houver risco explícito."
            impact = "A ação específica não foi concluída nesta tentativa."
        return {
            "mode": "self-healing", "exit_code": 1, "summary": summary,
            "client_report": (
                "Resumo para o cliente\n" + decision.message + "\n\n"
                "O que encontramos\n" + f"Categoria identificada: {decision.category}.\n" + f"Diagnóstico técnico: {diagnostic}\n\n"
                "Impacto\n" + impact + "\n\nPróximo passo\n" + next_step
            ),
            "stderr": diagnostic,
            "self_healing": {
                "status": decision.status,
                "category": decision.category,
                "requires_authorization": decision.requires_authorization,
                "strategy": decision.strategy,
                "message": decision.message,
                "steps": decision.steps,
                "hard_stop": decision.hard_stop,
                "pipeline_continued": False,
            },
        }

    def _recover_github_access(self, project: Project, execution_attempt: int) -> RecoveryDecision:
        """Resolve repository access exclusively with GitHub credentials stored by DevPilot.

        End users never need to authenticate GitHub for a project execution. The project organization
        credential is only a preference; every enabled GitHub credential from the same workspace is
        eligible for bounded failover.
        """
        steps = []
        with SessionLocal() as db:
            organization = db.get(Organization, project.organization_id) if project.organization_id else None
            credentials = list(
                db.scalars(
                    select(ProviderCredential).where(
                        ProviderCredential.workspace_id == project.workspace_id,
                        ProviderCredential.provider == "github",
                        ProviderCredential.enabled.is_(True),
                    )
                ).all()
            )
            preferred_credential_id = organization.credential_id if organization else None
            credentials.sort(key=lambda item: (item.id != preferred_credential_id, item.id))

            if not credentials:
                return RecoveryDecision(
                    "github_auth",
                    "needs_attention",
                    "Nenhuma credencial GitHub administrativa está cadastrada e ativa neste workspace.",
                    False,
                    False,
                    "github_credentials_missing_admin",
                    steps,
                )

            for index, credential in enumerate(credentials[:self.MAX_ATTEMPTS], start=1):
                try:
                    token = Vault().decrypt(credential.encrypted_secret)
                except ValueError:
                    steps.append({
                        "state": "credential_invalid",
                        "attempt": execution_attempt,
                        "credential": credential.label,
                        "candidate": index,
                        "message": "A credencial cadastrada não pôde ser descriptografada e foi ignorada.",
                    })
                    continue

                result = self._git_ls_remote(project.repository_url, token)
                if result.returncode == 0:
                    changed = bool(organization and organization.credential_id != credential.id)
                    if changed:
                        organization.credential_id = credential.id
                        organization.last_sync_error = ""
                        db.commit()
                    return RecoveryDecision(
                        "github_auth",
                        "resolved",
                        "Acesso ao GitHub restabelecido com uma credencial já cadastrada no DevPilot."
                        if changed or preferred_credential_id is None
                        else "A credencial GitHub cadastrada foi validada novamente e o acesso está disponível.",
                        execution_attempt < self.MAX_ATTEMPTS,
                        False,
                        "github_credential_failover" if changed or preferred_credential_id is None else "github_access_recheck",
                        steps,
                    )

                steps.append({
                    "state": "credential_rejected",
                    "attempt": execution_attempt,
                    "credential": credential.label,
                    "candidate": index,
                    "message": "A credencial cadastrada não possui acesso suficiente ao repositório.",
                })

            return RecoveryDecision(
                "github_auth",
                "needs_attention",
                "As credenciais GitHub cadastradas no DevPilot foram testadas e nenhuma possui acesso ao repositório.",
                False,
                False,
                "github_credentials_exhausted_admin",
                steps,
            )

    def _git_ls_remote(self, repository_url: str, token: str) -> subprocess.CompletedProcess[str]:
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode(); env = os.environ.copy()
        env.update({"GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"http.extraHeader","GIT_CONFIG_VALUE_0":f"Authorization: Basic {encoded}"})
        return subprocess.run(["git","ls-remote",repository_url,"HEAD"], text=True, capture_output=True, timeout=45, check=False, env=env)

    def _quarantine_invalid_repository(self, project: Project) -> bool:
        path = get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)
        if not path.exists() or (path / ".git").exists(): return False
        try: path.rename(self._available_recovery_path(path)); return True
        except OSError: return False

    def _available_recovery_path(self, path: Path) -> Path:
        for suffix in range(1,100):
            candidate = path.with_name(f"{path.name}.recovery-{suffix}")
            if not candidate.exists(): return candidate
        raise OSError("No recovery path available")

    def _safe_error(self, value: str, limit: int = 2400) -> str:
        """Preserve enough sanitized context for classification and diagnosis instead of only the final line."""
        text = str(value or "").strip()
        for pattern in _SECRET_PATTERNS:
            replacement = r"\1[REDACTED]" if pattern is _SECRET_PATTERNS[0] else "[REDACTED]"
            text = pattern.sub(replacement, text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines: return "Falha sem mensagem detalhada."
        compact = "\n".join(lines)
        if len(compact) <= limit: return compact
        half = max(200, (limit - 40) // 2)
        return f"{compact[:half]}\n... [contexto reduzido] ...\n{compact[-half:]}"
