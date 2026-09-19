from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential, Task
from app.services.vault import Vault


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
READ_ONLY_MODE_MARKER = "[DEVPILOT_MODE=analysis-read-only]"
CLIENT_REPORT_INSTRUCTIONS = (
    "IMPORTANT FINAL RESPONSE FORMAT. Your final answer is shown directly to a non-technical client. "
    "Write the final answer in Brazilian Portuguese, using clear business language and no raw JSON, "
    "terminal dumps, stack traces, or large source-code excerpts. Technical names may be mentioned only "
    "when needed to explain the finding. Use exactly these sections: 'Resumo para o cliente', "
    "'O que encontramos', 'Impacto', 'Recomendações' and 'Próximo passo'. In 'Resumo para o cliente', "
    "explain in 2 to 4 sentences whether the project is healthy, needs attention, or has a blocking issue. "
    "In 'O que encontramos', list the most important concrete findings. In 'Impacto', explain what they "
    "mean for the product or operation. In 'Recomendações', prioritize the actions. In 'Próximo passo', "
    "give one clear action the client can authorize next. Keep the report concise and understandable."
)
DEVELOPMENT_DUPLICATE_GUARD = (
    "MANDATORY FIRST PHASE — DUPLICATION PREFLIGHT. Before editing any file, inspect the repository "
    "for an existing implementation equivalent to the requested behavior. Check routes, screens, "
    "components, services, models, tests, configuration and documentation as relevant. Do not create "
    "a parallel or second implementation of behavior that already exists. If the feature already "
    "exists completely, make no implementation change merely to satisfy the task: validate it with "
    "the relevant checks and report the evidence. If it exists partially, reuse and extend the "
    "existing implementation and change only the verified gaps. Prefer adapting existing files and "
    "flows over adding duplicate endpoints, screens, components, services or models."
)
SYSTEM_DESIGN_GATE = (
    "MANDATORY SECOND PHASE — SYSTEM DESIGN GATE. Complete this phase before editing any file. "
    "Classify the requested change as SIMPLE or STRUCTURAL and state the classification with evidence. "
    "SIMPLE changes are narrowly scoped presentation or content changes that do not alter architecture, "
    "data contracts, persistence, authentication, authorization, integrations, infrastructure, AI behavior, "
    "multi-tenancy, background processing, queues, concurrency, deployment topology, or externally consumed APIs. "
    "For a SIMPLE change, explicitly record 'System Design dispensado' and the reason before implementation. "
    "A STRUCTURAL change requires a concise System Design before implementation. The design must cover affected "
    "architecture, component responsibilities, API/contracts, data model and migrations, authentication and "
    "authorization, external dependencies, concurrency/queues when applicable, failure handling and recovery, "
    "security and tenant isolation, scalability/capacity considerations, observability, deployment strategy, "
    "backward compatibility, rollback, and the tests needed to validate the change. Identify material risks and "
    "trade-offs. Reuse the current architecture unless there is concrete evidence that it must change. Only after "
    "the System Design is complete (or a SIMPLE-change waiver is justified) may implementation begin."
)
AGENTS_FILE_NAME = "AGENTS.md"
GENERATED_AGENTS_START = "<!-- DEVPILOT-GENERATED-ANALYSIS:START -->"
GENERATED_AGENTS_END = "<!-- DEVPILOT-GENERATED-ANALYSIS:END -->"
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def run(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if env_overrides:
        environment.update(env_overrides)
    environment.setdefault("CI", "1")
    environment.setdefault("DEBIAN_FRONTEND", "noninteractive")
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=environment,
    )


def github_basic_authorization(access_token: str) -> str:
    encoded = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    return f"Authorization: Basic {encoded}"


def git_environment(project: Project) -> dict[str, str]:
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    if not project.organization_id:
        return environment

    with SessionLocal() as db:
        organization = db.scalar(
            select(Organization).where(Organization.id == project.organization_id)
        )
        if not organization or not organization.credential_id:
            return environment
        credential = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.id == organization.credential_id,
                ProviderCredential.provider == "github",
                ProviderCredential.enabled.is_(True),
            )
        )
        if not credential:
            return environment
        try:
            access_token = Vault().decrypt(credential.encrypted_secret)
        except ValueError as error:
            raise RuntimeError("GitHub organization credential cannot be decrypted") from error

    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": github_basic_authorization(access_token),
        }
    )
    return environment


def ensure_repository(project: Project) -> Path:
    path = repository_path(project)
    git_env = git_environment(project)
    if not path.exists():
        result = run(
            ["git", "clone", "--filter=blob:none", project.repository_url, str(path)],
            env_overrides=git_env,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Unable to clone repository")
    result = run(["git", "fetch", "--prune", "origin"], cwd=path, env_overrides=git_env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to fetch repository")
    return path


def is_read_only_task(task: Task) -> bool:
    prompt = str(task.prompt or "")
    normalized = prompt.casefold()
    return READ_ONLY_MODE_MARKER.casefold() in normalized or "não modifique arquivos" in normalized


def codex_command(project: Project, prompt: str) -> list[str]:
    config = json.loads(project.codex_config or "{}")
    command = ["codex", "exec", "--json"]
    if model := config.get("model"):
        command.extend(["--model", str(model)])
    command.append(prompt)
    return command


def task_timeout(project: Project) -> int:
    config = json.loads(project.codex_config or "{}")
    return int(config.get("timeout_seconds", 1800))


def _extract_text(value) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        clean = value.strip()
        if clean:
            texts.append(clean)
        return texts
    if isinstance(value, list):
        for item in value:
            texts.extend(_extract_text(item))
        return texts
    if not isinstance(value, dict):
        return texts

    item_type = str(value.get("type") or "").lower()
    if item_type in {"agent_message", "assistant_message", "output_text"}:
        for key in ("text", "content", "message", "output_text"):
            if key in value:
                texts.extend(_extract_text(value[key]))
        return texts

    for key in ("item", "message", "response", "output"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            texts.extend(_extract_text(nested))
    return texts


def extract_client_report(stdout: str) -> str:
    """Extract the final human-facing Codex message from JSONL output."""
    candidates: list[str] = []
    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        candidates.extend(_extract_text(payload))

    for text in reversed(candidates):
        normalized = text.strip()
        if len(normalized) < 40:
            continue
        if "Resumo para o cliente" in normalized or "O que encontramos" in normalized:
            return normalized[-30_000:]

    return candidates[-1][-30_000:] if candidates else ""


def development_prompt(task: Task) -> str:
    return (
        f"Task: {task.title}\n\n{task.prompt}\n\n"
        f"{DEVELOPMENT_DUPLICATE_GUARD}\n\n"
        f"{SYSTEM_DESIGN_GATE}\n\n"
        "Only after completing both mandatory phases, implement the smallest complete change that is still "
        "necessary, run relevant checks, and summarize the duplication preflight, System Design decision, "
        "changes and remaining risks. Do not push or merge.\n\n"
        f"{CLIENT_REPORT_INSTRUCTIONS}"
    )


def _redact_generated_text(value: str) -> str:
    text = str(value or "")
    text = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", text)
    for pattern in _SECRET_PATTERNS[1:]:
        text = pattern.sub("[REDACTED]", text)
    return text


def _without_generated_agents_section(value: str) -> str:
    text = str(value or "")
    start = text.find(GENERATED_AGENTS_START)
    if start < 0:
        return text.strip()
    end = text.find(GENERATED_AGENTS_END, start + len(GENERATED_AGENTS_START))
    if end < 0:
        return text[:start].rstrip()
    return (text[:start] + text[end + len(GENERATED_AGENTS_END):]).strip()


def build_generated_agents_md(
    project: Project,
    task: Task,
    report: str,
    base_content: str = "",
) -> str:
    base = _without_generated_agents_section(base_content or project.agents_md)
    if not base:
        base = (
            "# Instruções do projeto\n\n"
            "Este arquivo foi criado pelo DevPilot e reúne orientações para futuras tarefas.\n"
        )

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    safe_report = _redact_generated_text(report).strip()
    if not safe_report:
        safe_report = "A análise detalhada ainda não foi disponibilizada."

    section = f"""
{GENERATED_AGENTS_START}
## Orientações geradas pelo DevPilot

- Projeto: {project.name}
- Repositório: {project.repository_url}
- Branch de referência: {project.default_branch}
- Última atualização: {generated_at}
- Tarefa de origem: {task.title}

### Diretrizes para futuras tarefas

- Faça uma preflight de duplicidade antes de criar qualquer implementação.
- Antes de implementar, classifique a mudança como SIMPLE ou STRUCTURAL para fins de System Design.
- Para mudança STRUCTURAL, documente arquitetura, componentes, contratos, dados, segurança, falhas, escalabilidade, observabilidade, deploy e rollback antes de editar arquivos.
- Para mudança SIMPLE, registre explicitamente "System Design dispensado" e a justificativa antes de editar arquivos.
- Preserve a arquitetura e os padrões já existentes no projeto.
- Execute os testes e validações relevantes antes de concluir.
- Nunca exponha credenciais, dados pessoais ou segredos nos logs, commits ou relatórios.
- Não faça push, merge, deploy ou operações destrutivas sem aprovação explícita.

### Evidências da última análise

{safe_report}
{GENERATED_AGENTS_END}
"""
    return f"{base.rstrip()}\n\n{section.strip()}\n"


def write_generated_agents_md(
    repository: Path,
    project: Project,
    task: Task,
    report: str,
) -> str:
    """Persist only the generated instruction file, never disposable analysis-worktree changes."""
    target = repository / AGENTS_FILE_NAME
    temporary = target.with_name(f".{target.name}.{task.id[:8]}.tmp")
    try:
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        content = build_generated_agents_md(project, task, report, existing)
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, target)
        project.agents_md = content
        return content
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"Unable to generate {AGENTS_FILE_NAME}: {error}") from error


def execute_read_only_analysis(project: Project, task: Task, repository: Path) -> dict:
    """Run analysis in a disposable worktree so tracked project files are never persisted."""
    with tempfile.TemporaryDirectory(prefix=f"devpilot-analysis-{task.id[:8]}-") as temp_dir:
        analysis_path = Path(temp_dir) / "repository"
        worktree = run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(analysis_path),
                f"origin/{project.default_branch}",
            ],
            cwd=repository,
        )
        if worktree.returncode:
            raise RuntimeError(worktree.stderr.strip() or "Unable to prepare isolated analysis workspace")

        try:
            rules = (
                f"\n\nProject instructions (reference only):\n{project.agents_md}"
                if project.agents_md
                else ""
            )
            prompt = (
                f"Task: {task.title}\n\n{task.prompt}{rules}\n\n"
                "This is a READ-ONLY ANALYSIS. Inspect the repository and produce a technical report "
                "with concrete evidence, risks, impact, recommendations, and estimated effort. Include an "
                "architecture assessment and identify which recommended changes would require a STRUCTURAL "
                "System Design before implementation. Do not implement, edit, create, delete, rename, commit, "
                "push, or merge project files. If a change would be useful, describe it instead of applying it.\n\n"
                f"{CLIENT_REPORT_INSTRUCTIONS}"
            )
            result = run(
                codex_command(project, prompt),
                cwd=analysis_path,
                timeout=task_timeout(project),
            )
            status = run(["git", "status", "--porcelain"], cwd=analysis_path)
            attempted_changes = bool(status.stdout.strip()) if status.returncode == 0 else None
            client_report = extract_client_report(result.stdout)
            return {
                "mode": "analysis-read-only",
                "exit_code": result.returncode,
                "summary": (
                    "Análise concluída. O relatório para o cliente está disponível abaixo."
                    if result.returncode == 0
                    else "A análise terminou com falha; consulte o diagnóstico e os detalhes técnicos."
                ),
                "client_report": client_report,
                "stdout": result.stdout[-100_000:],
                "stderr": result.stderr[-20_000:],
                "attempted_changes": attempted_changes,
                "persisted_changes": False,
                "branch": "",
            }
        finally:
            run(["git", "worktree", "remove", "--force", str(analysis_path)], cwd=repository)
            run(["git", "worktree", "prune"], cwd=repository)


def execute_task(project: Project, task: Task) -> dict:
    settings = get_settings()
    read_only = is_read_only_task(task)

    if read_only:
        path = ensure_repository(project)
        write_generated_agents_md(
            path,
            project,
            task,
            "A análise foi solicitada e o arquivo de instruções foi preparado. "
            "A auditoria detalhada será registrada quando o analisador estiver habilitado.",
        )
        if not settings.execution_enabled:
            return {
                "mode": "analysis-read-only-disabled",
                "exit_code": 0,
                "summary": (
                    "AGENTS.md foi gerado. A execução automática está desativada; "
                    "a auditoria detalhada aguarda habilitação."
                ),
                "client_report": (
                    "Resumo para o cliente\n"
                    "O arquivo de instruções do projeto foi gerado com segurança. "
                    "A análise detalhada ainda não foi executada porque a execução automática está desativada.\n\n"
                    "O que encontramos\n"
                    "O DevPilot preparou o AGENTS.md com as regras operacionais básicas do projeto.\n\n"
                    "Impacto\n"
                    "As próximas tarefas já poderão usar essas orientações quando a execução for habilitada.\n\n"
                    "Recomendações\n"
                    "Habilitar a execução para concluir a auditoria técnica.\n\n"
                    "Próximo passo\n"
                    "Habilite a execução automática e solicite novamente a análise."
                ),
                "agents_md_generated": True,
                "agents_md_path": AGENTS_FILE_NAME,
            }

        result = execute_read_only_analysis(project, task, path)
        write_generated_agents_md(
            path,
            project,
            task,
            result.get("client_report") or result.get("summary", ""),
        )
        result["agents_md_generated"] = True
        result["agents_md_path"] = AGENTS_FILE_NAME
        if result.get("exit_code", 1) == 0:
            result["summary"] = (
                "Análise concluída e AGENTS.md gerado/atualizado. "
                "O relatório para o cliente está disponível abaixo."
            )
        else:
            result["summary"] = (
                f"{result.get('summary', 'A análise terminou com falha.')} "
                "O AGENTS.md foi preservado com o contexto disponível."
            )
        return result

    if not settings.execution_enabled:
        return {
            "mode": "dry-run",
            "summary": "A execução está desativada. A tarefa foi registrada e aguarda execução habilitada.",
            "client_report": (
                "Resumo para o cliente\nA solicitação foi registrada, mas a execução automática está desativada.\n\n"
                "O que encontramos\nAinda não houve execução do repositório.\n\n"
                "Impacto\nNenhuma alteração foi aplicada ao projeto.\n\n"
                "Recomendações\nHabilitar a execução para permitir o desenvolvimento.\n\n"
                "Próximo passo\nAutorize ou habilite a execução da tarefa."
            ),
            "planned_command": ["codex", "exec", "--json", "<task prompt>"],
        }

    path = ensure_repository(project)
    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    checkout = run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=path)
    if checkout.returncode:
        raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")
    result = run(
        codex_command(project, development_prompt(task)),
        cwd=path,
        timeout=task_timeout(project),
    )
    client_report = extract_client_report(result.stdout)
    return {
        "mode": "execute",
        "exit_code": result.returncode,
        "summary": (
            "Execução concluída. Veja abaixo o resultado em linguagem de cliente."
            if result.returncode == 0
            else "A execução terminou com falha; consulte o diagnóstico e os detalhes técnicos."
        ),
        "client_report": client_report,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }
