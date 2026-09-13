from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.models import TaskStatus


AI_ESCALATION_MARKER = "[DEVPILOT_AI_LAST_RESORT_ESCALATION]"


def _safe_text(value: object, limit: int = 6000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n... [contexto reduzido]"


def install_ai_last_resort_recovery() -> None:
    """Guarantee that recoverable failures reach the AI before a human is asked.

    Deterministic self-healing still runs first. If it cannot resolve the problem, a
    normal failure-recovery task is queued automatically. When that recovery task is
    itself unable to reach the repository, the AI receives the available failure
    context in an isolated workspace and performs a final read-only diagnosis. Human
    intervention is surfaced only after this bounded AI stage concludes that no
    verifiable automatic repair can be completed from the current environment.
    """
    from app.services import executor
    from app.services import failure_recovery
    from app.services.recovery import AutoRecoveryService, RecoveryDecision

    current_execute = executor.execute_task
    if not getattr(current_execute, "_devpilot_ai_last_resort", False):
        def execute_task(project, task):
            if not failure_recovery.is_failure_recovery_task(task):
                return current_execute(project, task)

            try:
                return current_execute(project, task)
            except Exception as original_error:
                category = AutoRecoveryService().classify(str(original_error))
                prompt = (
                    "MISSÃO DE ÚLTIMA INSTÂNCIA DA IA\n"
                    "Uma recuperação automática já foi criada porque a execução original falhou. "
                    "Os reparos determinísticos disponíveis também não conseguiram concluir a tarefa. "
                    "Antes de envolver uma pessoa, faça um diagnóstico final usando somente as informações "
                    "disponíveis. Não invente sucesso e não peça credenciais que já deveriam estar cadastradas.\n\n"
                    "REGRAS\n"
                    "1. Analise a causa raiz e diferencie falha interna reparável de dependência externa real.\n"
                    "2. Considere credenciais já cadastradas, configuração, rede, checkout, permissões, banco, "
                    "dependências e estado do ambiente.\n"
                    "3. Não execute operações destrutivas e não altere permissões globais.\n"
                    "4. Se houver uma correção automática verificável que dependa do repositório, descreva-a com "
                    "precisão; o DevPilot repetirá a execução quando o ambiente estiver apto.\n"
                    "5. Só conclua que é necessária intervenção humana quando faltar uma capacidade externa que "
                    "o sistema realmente não possui, como conceder acesso, fornecer uma credencial inexistente, "
                    "autorizar uma ação de alto risco ou tomar uma decisão de negócio.\n"
                    "6. Explique exatamente por que a automação não consegue ultrapassar essa fronteira.\n\n"
                    f"CATEGORIA INICIAL: {category}\n"
                    f"ERRO QUE IMPEDIU A RECUPERAÇÃO: {_safe_text(original_error)}\n\n"
                    f"CONTEXTO DA TAREFA DE RECUPERAÇÃO:\n{_safe_text(task.prompt, 20000)}\n\n"
                    f"{executor.CLIENT_REPORT_INSTRUCTIONS}"
                )

                with tempfile.TemporaryDirectory(prefix=f"devpilot-ai-recovery-{task.id[:8]}-") as temp_dir:
                    result = executor.run(
                        executor.codex_command(project, prompt),
                        cwd=Path(temp_dir),
                        timeout=executor.task_timeout(project),
                    )

                if result.returncode != 0:
                    # If the AI runtime itself is unavailable, preserve the original
                    # technical failure so the normal classifier can make the final
                    # decision without fabricating an AI diagnosis.
                    raise original_error

                report = executor.extract_client_report(result.stdout)
                return {
                    "mode": "ai-last-resort-diagnosis",
                    "exit_code": 78,
                    "summary": (
                        "A IA esgotou a análise automática disponível antes da escalada humana. "
                        "A execução continua bloqueada porque a correção não pôde ser verificada no ambiente atual."
                    ),
                    "client_report": report,
                    "stdout": result.stdout[-100_000:],
                    "stderr": (
                        f"{AI_ESCALATION_MARKER}\n"
                        f"category={category}\n"
                        f"original_error={_safe_text(original_error, 3000)}"
                    ),
                    "ai_recovery": {
                        "stage": "last_resort",
                        "diagnosed": True,
                        "category": category,
                        "human_only_after_ai": True,
                    },
                }

        setattr(execute_task, "_devpilot_ai_last_resort", True)
        executor.execute_task = execute_task

    current_recover = AutoRecoveryService.recover
    if not getattr(current_recover, "_devpilot_ai_last_resort", False):
        def recover(self, project, task, error_text, execution_attempt):
            if AI_ESCALATION_MARKER in str(error_text or ""):
                return RecoveryDecision(
                    category="external_dependency",
                    status="needs_authorization",
                    message=(
                        "A IA já analisou a falha após o esgotamento das correções automáticas e não conseguiu "
                        "comprovar uma solução executável com os recursos disponíveis. A intervenção humana agora "
                        "é a última instância."
                    ),
                    retry=False,
                    requires_authorization=True,
                    strategy="ai_last_resort_then_human",
                    steps=[{
                        "state": "ai_last_resort_completed",
                        "attempt": execution_attempt,
                        "message": "Diagnóstico final da IA concluído antes da escalada humana.",
                    }],
                )
            return current_recover(self, project, task, error_text, execution_attempt)

        setattr(recover, "_devpilot_ai_last_resort", True)
        AutoRecoveryService.recover = recover

    current_ensure = failure_recovery.ensure_failure_recovery_task
    if not getattr(current_ensure, "_devpilot_ai_last_resort", False):
        def ensure_failure_recovery_task(db, *, original_task, run, failure, actor="worker"):
            recovery = current_ensure(
                db,
                original_task=original_task,
                run=run,
                failure=failure,
                actor=actor,
            )
            if not recovery:
                return recovery

            category = str(failure.get("category") or "unknown").strip().lower()
            # The AI cannot diagnose its own missing runtime. For every other class,
            # including GitHub access, filesystem, network, database and unknown
            # failures, the automatic recovery task must run before a person is asked.
            if category != "codex_auth" and recovery.status in {
                TaskStatus.awaiting_approval,
                TaskStatus.blocked,
                TaskStatus.failed,
            }:
                now = datetime.now(timezone.utc)
                recovery.status = TaskStatus.queued
                recovery.requires_approval = False
                recovery.approved_at = recovery.approved_at or now
                recovery.updated_at = now
                db.flush()
            return recovery

        setattr(ensure_failure_recovery_task, "_devpilot_ai_last_resort", True)
        failure_recovery.ensure_failure_recovery_task = ensure_failure_recovery_task
