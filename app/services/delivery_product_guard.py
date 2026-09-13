from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.models import ProviderCredential, Task, TaskStatus
from app.services.audit import record
from app.services.vault import Vault


DELIVERY_REPAIR_MARKER = "[DEVPILOT_DELIVERY_REPAIR_V1]"
ACTIVE_TASK_STATES = {
    TaskStatus.queued,
    TaskStatus.planning,
    TaskStatus.running,
    TaskStatus.review,
    TaskStatus.awaiting_approval,
}
REPAIRABLE_TASK_STATES = {
    TaskStatus.completed,
    TaskStatus.failed,
    TaskStatus.blocked,
    TaskStatus.awaiting_approval,
}
MAX_SAFE_RETRIES = 3
APP_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "composer.json",
    "manage.py",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
    "index.html",
}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".vue",
    ".php",
    ".java",
    ".go",
    ".rs",
    ".html",
    ".css",
}
_IGNORED_PREFIXES = (".devpilot/", ".github/", "docs/")
_BASE_RUN_DELIVERY = None


def _github_token(db: Session, workspace_id: str) -> str:
    rows = list(
        db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider.in_(("github", "cloud:github")),
                ProviderCredential.enabled.is_(True),
            )
        ).all()
    )
    for row in rows:
        try:
            token = Vault().decrypt(row.encrypted_secret).strip()
        except (TypeError, ValueError):
            continue
        if token:
            return token
    return ""


def _repository_paths(db: Session, project) -> list[str] | None:
    """Return files from the remote default branch.

    Stored credentials are tried first so private repositories keep working. If that
    credential is stale or belongs to an account without access, retry anonymously.
    This lets public repositories remain inspectable instead of silently bypassing the
    product guard because of an unrelated credential problem.

    None means the guard could not inspect the remote safely, in which case the normal
    delivery path remains authoritative instead of producing a false blocker.
    """
    full_name = delivery.repository_full_name(db, project).strip("/")
    if full_name.count("/") != 1:
        return None

    branch = quote(str(project.default_branch or "main"), safe="")
    token = _github_token(db, project.workspace_id)
    base_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }
    candidates = [dict(base_headers)]
    if token:
        authenticated = dict(base_headers)
        authenticated["Authorization"] = f"Bearer {token}"
        candidates.insert(0, authenticated)

    response = None
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            for headers in candidates:
                response = client.get(
                    f"https://api.github.com/repos/{full_name}/git/trees/{branch}",
                    params={"recursive": "1"},
                    headers=headers,
                )
                if response.status_code == 200:
                    break
    except httpx.HTTPError:
        return None
    if response is None or response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    tree = payload.get("tree") if isinstance(payload, dict) else None
    if not isinstance(tree, list):
        return None
    return sorted(
        {
            str(item.get("path") or "").strip("/")
            for item in tree
            if isinstance(item, dict)
            and item.get("type") == "blob"
            and str(item.get("path") or "").strip()
        }
    )


def _is_application_file(path: str) -> bool:
    normalized = str(path or "").strip("/")
    if not normalized or normalized.startswith(_IGNORED_PREFIXES):
        return False
    name = normalized.rsplit("/", 1)[-1]
    if name in APP_FILENAMES:
        return True
    lower = normalized.lower()
    if lower in {"readme.md", "agents.md", "license", ".gitignore"}:
        return False
    return any(lower.endswith(extension) for extension in SOURCE_EXTENSIONS)


def _preflight_reasons(paths: list[str], requested: list[str]) -> list[str]:
    reasons: list[str] = []
    app_paths = [path for path in paths if _is_application_file(path)]
    requested_set = {str(item).strip().lower() for item in requested if item}

    if not app_paths:
        reasons.append(
            "O branch padrão remoto não contém aplicação executável; há apenas metadados/documentação ou arquivos auxiliares."
        )

    if "render" in requested_set and "Dockerfile" not in paths:
        reasons.append(
            "O backend será publicado no Render, mas o contrato atual de entrega usa Docker e o branch padrão remoto não possui Dockerfile."
        )

    if "vercel" in requested_set:
        frontend_markers = {
            "package.json",
            "index.html",
            "frontend/package.json",
            "web/package.json",
            "client/package.json",
        }
        if not frontend_markers.intersection(paths):
            has_frontend_source = any(
                path.lower().endswith((".html", ".tsx", ".jsx", ".vue"))
                for path in app_paths
            )
            if not has_frontend_source:
                reasons.append(
                    "A entrega solicita Vercel, mas o branch padrão remoto não contém um frontend publicável identificável."
                )

    return reasons


def _requirements_context(db: Session, project) -> str:
    tasks = list(
        db.scalars(
            select(Task)
            .where(
                Task.project_id == project.id,
                Task.workspace_id == project.workspace_id,
                Task.source.notin_(("failure-recovery", "delivery-recovery")),
            )
            .order_by(Task.created_at.asc())
            .limit(40)
        ).all()
    )
    chunks: list[str] = []
    total = 0
    for index, task in enumerate(tasks, start=1):
        prompt = " ".join(str(task.prompt or "").split())
        prompt = prompt[:3500]
        chunk = f"\n### Requisito/Tarefa {index}: {task.title}\n{prompt}\n"
        if total + len(chunk) > 55_000:
            break
        chunks.append(chunk)
        total += len(chunk)
    if not chunks:
        return f"Projeto: {project.name}\nDescrição: {project.description or '(sem descrição)'}"
    return "".join(chunks)


def _latest_repair(db: Session, project) -> Task | None:
    return db.scalar(
        select(Task)
        .where(
            Task.project_id == project.id,
            Task.workspace_id == project.workspace_id,
            Task.source == "delivery-recovery",
            Task.prompt.contains(DELIVERY_REPAIR_MARKER),
        )
        .order_by(Task.created_at.desc())
        .limit(1)
    )


def _retry_count(task: Task) -> int:
    return str(task.prompt or "").count("[delivery-repair-retry:")


def _repair_prompt(db: Session, project, reasons: list[str], paths: list[str]) -> str:
    requested = delivery.selected_providers(project)
    evidence = "\n".join(f"- {reason}" for reason in reasons)
    sample = "\n".join(f"- {path}" for path in paths[:80]) or "- branch remoto sem arquivos de aplicação"
    requirements = _requirements_context(db, project)
    return (
        f"{DELIVERY_REPAIR_MARKER}\n"
        "[DEVPILOT_MODE=fix]\n"
        "[DEVPILOT_DELIVERY_REQUIRES_REMOTE_PROOF=true]\n\n"
        "MISSÃO DE RECUPERAÇÃO DA ENTREGA FINAL\n"
        "O jogo marcou as fases como concluídas, porém a validação do produto real provou que o branch padrão remoto ainda não contém uma entrega publicável. "
        "Sua responsabilidade é chegar ao produto solicitado pelo usuário no início, não apenas corrigir a mensagem de deploy.\n\n"
        "EVIDÊNCIAS DO IMPEDIMENTO\n"
        f"{evidence}\n\n"
        "ESTADO REMOTO OBSERVADO\n"
        f"{sample}\n\n"
        f"PROVEDORES DE ENTREGA NECESSÁRIOS: {', '.join(requested) or 'detecção automática'}\n\n"
        "PROTOCOLO OBRIGATÓRIO\n"
        "1. Leia AGENTS.md e todos os requisitos/tarefas abaixo; trate-os como a fonte do escopo originalmente solicitado.\n"
        "2. Inspecione o branch padrão remoto e qualquer trabalho útil deixado em worktree/branch temporário. Recupere trabalho válido em vez de recomeçar sem necessidade.\n"
        "3. Se o sistema não existir no repositório, implemente o produto real. Não aceite README, placeholder, mock vazio ou arquivo de estado como entrega.\n"
        "4. Preserve todas as funcionalidades pedidas nas fases anteriores e corrija inconsistências encontradas durante a revisão.\n"
        "5. Se Render fizer parte da entrega, garanta um Dockerfile funcional, comando de inicialização correto e endpoint /health.\n"
        "6. Se Vercel fizer parte da entrega, garanta um frontend realmente compilável/publicável e integração correta com o backend quando existir.\n"
        "7. Execute testes, lint/typecheck/build aplicáveis e um smoke test do fluxo principal solicitado pelo usuário.\n"
        "8. Não grave segredos no repositório. Use variáveis de ambiente para credenciais e URLs sensíveis.\n"
        "9. O critério de sucesso é REMOTO: os arquivos necessários precisam existir no branch consumido pela entrega. Não conclua deixando a solução somente no workspace local, worktree descartável ou branch não publicado.\n"
        "10. Ao final, revise novamente o objetivo original e confirme que o sistema entregue corresponde ao pedido, não apenas que o deploy passou.\n\n"
        "REQUISITOS ORIGINAIS RECUPERADOS DO PROJETO\n"
        f"{requirements}"
    )[:100_000]


def _ensure_repair_task(
    db: Session,
    project,
    reasons: list[str],
    paths: list[str],
    actor: str,
) -> tuple[Task, bool]:
    existing = _latest_repair(db, project)
    now = datetime.now(timezone.utc)
    if existing and existing.status in ACTIVE_TASK_STATES:
        if existing.status == TaskStatus.awaiting_approval and not existing.requires_approval:
            existing.status = TaskStatus.queued
            existing.approved_at = existing.approved_at or now
            existing.updated_at = now
            db.commit()
        return existing, False

    if existing and existing.status in REPAIRABLE_TASK_STATES and _retry_count(existing) < MAX_SAFE_RETRIES:
        retry = _retry_count(existing) + 1
        existing.prompt = (
            f"{str(existing.prompt or '').rstrip()}\n\n"
            f"[delivery-repair-retry:{retry}]\n"
            "A prova remota ainda falhou depois da tentativa anterior. Reavalie o estado atual, encontre a causa que impediu a materialização/publicação no branch padrão e corrija-a antes de concluir.\n"
            + "\n".join(f"- {reason}" for reason in reasons)
        )[:100_000]
        existing.status = TaskStatus.queued
        existing.requires_approval = False
        existing.approved_at = existing.approved_at or now
        existing.updated_at = now
        db.commit()
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=existing.id,
            actor=actor,
            action="project.delivery_repair_requeued",
            outcome="queued",
            details={"retry": retry, "reasons": reasons[:6]},
        )
        db.commit()
        return existing, True

    repair = Task(
        workspace_id=project.workspace_id,
        owner_user_id=project.owner_user_id,
        project_id=project.id,
        title=f"Recuperar entrega final · {project.name}"[:240],
        prompt=_repair_prompt(db, project, reasons, paths),
        source="delivery-recovery",
        status=TaskStatus.queued,
        priority=100,
        branch_name=str(project.default_branch or "main"),
        requires_approval=False,
        approved_at=now,
    )
    db.add(repair)
    db.flush()
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        task_id=repair.id,
        actor=actor,
        action="project.delivery_repair_created",
        outcome="queued",
        details={"reasons": reasons[:6], "remote_file_count": len(paths)},
    )
    db.commit()
    return repair, True


def _state_for_repair(db: Session, project, actor: str, reasons: list[str], paths: list[str]) -> dict:
    repair, changed = _ensure_repair_task(db, project, reasons, paths, actor)
    state = delivery.initial_delivery(project)
    exhausted = repair.status in {TaskStatus.failed, TaskStatus.blocked} and _retry_count(repair) >= MAX_SAFE_RETRIES
    state["status"] = "blocked" if exhausted else "repairing"
    state["delivery_gate"] = "repairing_product" if not exhausted else "repair_exhausted"
    state["repair_task_id"] = repair.id
    state["repair_task_status"] = repair.status.value
    state["repair_reasons"] = reasons[:8]
    state["repository_preflight"] = {
        "ok": False,
        "remote_file_count": len(paths),
        "reasons": reasons[:8],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    state["url"] = ""
    state["last_error"] = (
        "A autocorreção da entrega esgotou as tentativas seguras; intervenção humana é o último recurso."
        if exhausted
        else "O DevPilot detectou que o produto final ainda não está materializado no branch remoto e iniciou a correção automática."
    )
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    delivery.save_delivery(db, project, state)
    if changed:
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            task_id=repair.id,
            actor=actor,
            action="project.delivery_product_guard",
            outcome=state["status"],
            details={"reasons": reasons[:6]},
        )
        db.commit()
    return state


def _active_repair_state(db: Session, project) -> dict | None:
    state = delivery.initial_delivery(project)
    if str(state.get("status") or "").lower() != "repairing":
        return None
    repair_id = str(state.get("repair_task_id") or "").strip()
    if not repair_id:
        return None
    task = db.get(Task, repair_id)
    if not task or task.workspace_id != project.workspace_id or task.project_id != project.id:
        return None
    if task.status not in ACTIVE_TASK_STATES:
        return None
    state["repair_task_status"] = task.status.value
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return state


def _run_delivery_with_product_guard(db: Session, project, actor: str) -> dict:
    active = _active_repair_state(db, project)
    if active is not None:
        return active

    requested = delivery.selected_providers(project)
    paths = _repository_paths(db, project)
    if paths is not None:
        reasons = _preflight_reasons(paths, requested)
        if reasons:
            return _state_for_repair(db, project, actor, reasons, paths)

    if _BASE_RUN_DELIVERY is None:
        raise RuntimeError("delivery guard not installed")
    state = _BASE_RUN_DELIVERY(db, project, actor)
    if paths is not None:
        state["repository_preflight"] = {
            "ok": True,
            "remote_file_count": len(paths),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        delivery.save_delivery(db, project, state)
    return state


def install_delivery_product_guard() -> None:
    global _BASE_RUN_DELIVERY
    current = delivery.run_delivery
    if getattr(current, "_devpilot_delivery_product_guard", False):
        return
    _BASE_RUN_DELIVERY = current
    setattr(_run_delivery_with_product_guard, "_devpilot_delivery_product_guard", True)
    delivery.run_delivery = _run_delivery_with_product_guard
