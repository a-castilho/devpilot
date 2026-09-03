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

    def to_dict(self) -> dict:
        return asdict(self)


class AutoRecoveryService:
    """Safe, bounded recovery for failures that can be repaired without destructive actions."""

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

    def classify(self, error_text: str) -> str:
        text = str(error_text or "").casefold()
        if any(pattern in text for pattern in self._GITHUB_AUTH): return "github_auth"
        if any(pattern in text for pattern in self._NETWORK): return "git_network"
        if any(pattern in text for pattern in self._REPOSITORY_STATE): return "repository_state"
        if any(pattern in text for pattern in self._CODEX_AUTH): return "codex_auth"
        if any(pattern in text for pattern in self._DATABASE): return "database"
        if any(pattern in text for pattern in self._FILESYSTEM): return "filesystem_permission"
        return "unknown"

    def recover(self, project: Project, task: Task, error_text: str, execution_attempt: int) -> RecoveryDecision:
        category = self.classify(error_text)
        detected = {"state": "detected", "attempt": execution_attempt, "category": category, "message": self._safe_error(error_text)}
        if category == "github_auth":
            decision = self._recover_github_access(project, execution_attempt); decision.steps.insert(0, detected); return decision
        if category == "git_network" and execution_attempt < self.MAX_ATTEMPTS:
            delay = min(2, max(1, execution_attempt)); time.sleep(delay)
            return RecoveryDecision(category, "retrying", "Falha transitória de rede detectada. O DevPilot tentará novamente automaticamente.", True, False, "bounded_retry", [detected, {"state":"repairing","attempt":execution_attempt,"message":f"Nova tentativa agendada após {delay}s."}])
        if category == "repository_state":
            repaired = self._quarantine_invalid_repository(project)
            return RecoveryDecision(category, "resolved" if repaired else "needs_attention", "Área local inconsistente isolada com segurança. O DevPilot retomará a tarefa." if repaired else "O repositório local exige verificação antes de uma correção automática segura.", repaired and execution_attempt < self.MAX_ATTEMPTS, False, "quarantine_invalid_checkout" if repaired else "manual_repository_review", [detected])
        if category == "codex_auth":
            return RecoveryDecision(category, "needs_authorization", "O Codex não está autenticado no ambiente de execução. É necessária autorização para continuar.", False, True, "request_codex_authorization", [detected])
        if category == "filesystem_permission":
            return RecoveryDecision(category, "needs_authorization", "Permissão do sistema operacional bloqueou a execução. O DevPilot não alterou permissões automaticamente.", False, True, "request_filesystem_authorization", [detected])
        if category == "database":
            return RecoveryDecision(category, "needs_attention", "Falha de banco detectada. A correção automática foi interrompida para evitar operações inseguras sobre dados.", False, False, "database_safety_stop", [detected])
        return RecoveryDecision(
            category="unknown", status="diagnosis_required",
            message="Não foi possível identificar automaticamente a causa da falha. O erro original foi preservado para diagnóstico; nenhuma autorização será solicitada sem evidência de credencial ou permissão.",
            retry=False, requires_authorization=False, strategy="diagnose_original_error", steps=[detected],
        )

    def failure_result(self, decision: RecoveryDecision, original_error: str) -> dict:
        diagnostic = self._safe_error(original_error)
        if decision.requires_authorization:
            summary = f"Intervenção autorizada necessária: {decision.message}"
            next_step = "Conclua somente a autorização indicada pelo diagnóstico; depois o DevPilot retomará o fluxo automaticamente."
            impact = "A tarefa foi interrompida porque o diagnóstico comprovou uma dependência de autorização ou permissão."
        elif decision.category == "unknown":
            summary = f"Diagnóstico necessário: {decision.message}"
            next_step = "Analise o erro técnico preservado abaixo. Só solicite intervenção humana se o diagnóstico comprovar uma dependência externa."
            impact = "A tarefa foi interrompida porque a causa ainda não foi classificada com segurança; isso não significa falta de autorização."
        else:
            summary = f"Atenção necessária: {decision.message}"
            next_step = "Aplique o ajuste indicado pelo diagnóstico e repita a execução de forma controlada."
            impact = "A tarefa foi interrompida para evitar uma ação automática sem segurança comprovada."
        return {
            "mode": "self-healing", "exit_code": 1, "summary": summary,
            "client_report": (
                "Resumo para o cliente\n" + decision.message + "\n\n"
                "O que encontramos\n" + f"Categoria identificada: {decision.category}.\n" + f"Diagnóstico técnico: {diagnostic}\n\n"
                "Impacto\n" + impact + "\n\nPróximo passo\n" + next_step
            ),
            "stderr": diagnostic,
            "self_healing": {"status":decision.status,"category":decision.category,"requires_authorization":decision.requires_authorization,"strategy":decision.strategy,"message":decision.message,"steps":decision.steps},
        }

    def _recover_github_access(self, project: Project, execution_attempt: int) -> RecoveryDecision:
        steps = []
        if not project.organization_id:
            return RecoveryDecision("github_auth","needs_authorization","O projeto não possui uma organização GitHub com credencial configurada.",False,True,"request_github_authorization",steps)
        with SessionLocal() as db:
            organization = db.get(Organization, project.organization_id)
            if not organization: return RecoveryDecision("github_auth","needs_authorization","A organização GitHub vinculada ao projeto não foi encontrada.",False,True,"request_github_authorization",steps)
            credentials = list(db.scalars(select(ProviderCredential).where(ProviderCredential.workspace_id == project.workspace_id, ProviderCredential.provider == "github", ProviderCredential.enabled.is_(True))).all())
            credentials.sort(key=lambda item: item.id != organization.credential_id)
            if not credentials: return RecoveryDecision("github_auth","needs_authorization","Nenhuma credencial GitHub ativa está disponível para testar o acesso ao repositório.",False,True,"request_github_authorization",steps)
            for index, credential in enumerate(credentials[:self.MAX_ATTEMPTS], start=1):
                try: token = Vault().decrypt(credential.encrypted_secret)
                except ValueError: continue
                result = self._git_ls_remote(project.repository_url, token)
                if result.returncode == 0:
                    changed = organization.credential_id != credential.id
                    if changed: organization.credential_id = credential.id; organization.last_sync_error = ""; db.commit()
                    return RecoveryDecision("github_auth","resolved","Acesso ao GitHub restabelecido com uma credencial já autorizada." if changed else "A credencial GitHub foi validada novamente e o acesso está disponível.",execution_attempt < self.MAX_ATTEMPTS,False,"github_credential_failover" if changed else "github_access_recheck",steps)
                steps.append({"state":"credential_rejected","attempt":execution_attempt,"credential":credential.label,"candidate":index,"message":"A credencial não possui acesso suficiente ao repositório."})
            return RecoveryDecision("github_auth","needs_authorization","As credenciais GitHub disponíveis foram testadas e nenhuma possui acesso ao repositório.",False,True,"request_github_authorization",steps)

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
        # Keep both beginning and end: exception type/context is often at the start while root cause is at the end.
        half = max(200, (limit - 40) // 2)
        return f"{compact[:half]}\n... [contexto reduzido] ...\n{compact[-half:]}"
