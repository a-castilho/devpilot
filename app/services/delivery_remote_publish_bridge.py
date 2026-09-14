from __future__ import annotations

from app.models import Project, Task


_DELIVERY_SOURCE = "delivery-recovery"
_INSTALLED = False


def _failure(result: dict, message: str, *, stderr: str = "") -> dict:
    payload = dict(result or {})
    payload["exit_code"] = 75
    payload["summary"] = message
    payload["stderr"] = (str(payload.get("stderr") or "") + "\n" + str(stderr or "")).strip()[-20_000:]
    payload["delivery_remote_publish"] = {"ok": False, "message": message}
    return payload


def _run(executor, args: list[str], *, cwd, env=None, timeout: int = 180):
    return executor.run(args, cwd=cwd, timeout=timeout, env_overrides=env)


def _publish_delivery_recovery(project: Project, task: Task, result: dict) -> dict:
    """Materialize a successful delivery-recovery execution on the real remote branch.

    Normal development tasks remain local-first. Only the final-delivery recovery task
    is allowed to cross the remote boundary automatically because its persisted
    contract explicitly requires remote proof before the mission can be completed.
    """
    if task.source != _DELIVERY_SOURCE or int(result.get("exit_code", 0) or 0) != 0:
        return result

    from app.services import executor
    from app.services.github_access_bridge import resolve_github_access

    repository = executor.repository_path(project)
    if not (repository / ".git").exists():
        return _failure(result, "A correção terminou, mas o workspace Git da entrega não está disponível.")

    resolution = resolve_github_access(project)
    if not resolution.ok:
        return _failure(
            result,
            "A correção foi produzida, mas o DevPilot não conseguiu publicar no GitHub com uma credencial cadastrada válida.",
            stderr=resolution.message,
        )

    env = resolution.environment
    default_branch = str(project.default_branch or "main").strip() or "main"
    repository_url = executor.validated_repository_url(project)

    # Managed-local fallback may have created a repository without a real origin.
    remote = _run(executor, ["git", "remote", "get-url", "origin"], cwd=repository, env=env, timeout=30)
    if remote.returncode:
        added = _run(executor, ["git", "remote", "add", "origin", repository_url], cwd=repository, env=env, timeout=30)
        if added.returncode:
            return _failure(result, "Não foi possível vincular o workspace ao repositório remoto da entrega.", stderr=added.stderr)
    elif remote.stdout.strip() != repository_url:
        changed = _run(executor, ["git", "remote", "set-url", "origin", repository_url], cwd=repository, env=env, timeout=30)
        if changed.returncode:
            return _failure(result, "O origin local não pôde ser sincronizado com o repositório cadastrado.", stderr=changed.stderr)

    _run(executor, ["git", "config", "user.name", "DevPilot"], cwd=repository, env=env, timeout=30)
    _run(executor, ["git", "config", "user.email", "devpilot@local.invalid"], cwd=repository, env=env, timeout=30)

    status = _run(executor, ["git", "status", "--porcelain"], cwd=repository, env=env, timeout=30)
    if status.returncode:
        return _failure(result, "Não foi possível verificar os arquivos produzidos pela autocorreção.", stderr=status.stderr)

    if status.stdout.strip():
        staged = _run(executor, ["git", "add", "-A"], cwd=repository, env=env, timeout=60)
        if staged.returncode:
            return _failure(result, "A autocorreção produziu arquivos, mas eles não puderam ser preparados para publicação.", stderr=staged.stderr)
        committed = _run(
            executor,
            ["git", "commit", "-m", f"fix(delivery): materializar produto final ({task.id[:8]})"],
            cwd=repository,
            env=env,
            timeout=120,
        )
        if committed.returncode:
            return _failure(result, "A autocorreção produziu arquivos, mas o commit final falhou.", stderr=committed.stderr)

    # Always fetch the real branch before pushing. A managed-local workspace can have
    # started from a synthetic origin/main, so remote history must be joined instead
    # of force-pushing over existing commits.
    fetched = _run(executor, ["git", "fetch", "origin", default_branch], cwd=repository, env=env, timeout=180)
    if fetched.returncode:
        return _failure(result, "O produto foi corrigido localmente, mas o branch remoto não pôde ser atualizado antes da publicação.", stderr=fetched.stderr)

    remote_ref = f"origin/{default_branch}"
    ancestor = _run(executor, ["git", "merge-base", "HEAD", remote_ref], cwd=repository, env=env, timeout=30)
    if ancestor.returncode:
        merged = _run(
            executor,
            ["git", "merge", "--no-edit", "--allow-unrelated-histories", remote_ref],
            cwd=repository,
            env=env,
            timeout=180,
        )
    else:
        merged = _run(executor, ["git", "merge", "--no-edit", remote_ref], cwd=repository, env=env, timeout=180)
    if merged.returncode:
        _run(executor, ["git", "merge", "--abort"], cwd=repository, env=env, timeout=30)
        return _failure(result, "O DevPilot não conseguiu reconciliar com segurança o histórico remoto antes de publicar.", stderr=merged.stderr)

    # If Codex returned success without creating any product and HEAD still equals the
    # remote branch, do not manufacture a false successful delivery.
    ahead = _run(executor, ["git", "rev-list", "--count", f"{remote_ref}..HEAD"], cwd=repository, env=env, timeout=30)
    if ahead.returncode:
        return _failure(result, "Não foi possível confirmar se existe uma alteração real para publicar.", stderr=ahead.stderr)
    if int((ahead.stdout or "0").strip() or 0) <= 0:
        return _failure(
            result,
            "A autocorreção terminou sem materializar nenhuma alteração publicável no branch remoto.",
        )

    pushed = _run(
        executor,
        ["git", "push", "origin", f"HEAD:{default_branch}"],
        cwd=repository,
        env=env,
        timeout=240,
    )
    if pushed.returncode:
        return _failure(result, "O produto foi corrigido e commitado, mas o push para o branch de entrega falhou.", stderr=pushed.stderr)

    local_sha = _run(executor, ["git", "rev-parse", "HEAD"], cwd=repository, env=env, timeout=30)
    remote_sha = _run(executor, ["git", "ls-remote", "origin", f"refs/heads/{default_branch}"], cwd=repository, env=env, timeout=60)
    local_value = local_sha.stdout.strip() if local_sha.returncode == 0 else ""
    remote_value = (remote_sha.stdout.strip().split() or [""])[0] if remote_sha.returncode == 0 else ""
    if not local_value or local_value != remote_value:
        return _failure(result, "O push terminou, mas a prova remota do commit publicado não pôde ser confirmada.", stderr=remote_sha.stderr)

    payload = dict(result)
    payload["commit_sha"] = local_value
    payload["branch"] = default_branch
    payload["delivery_remote_publish"] = {
        "ok": True,
        "branch": default_branch,
        "commit_sha": local_value,
        "credential_id": resolution.credential_id,
        "remote_verified": True,
    }
    payload["summary"] = "Autocorreção concluída, commit publicada no branch remoto e prova GitHub confirmada."
    return payload


def install_delivery_remote_publish_bridge() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import executor

    current = executor.execute_task
    if getattr(current, "_devpilot_delivery_remote_publish", False):
        _INSTALLED = True
        return

    def execute_task(project: Project, task: Task) -> dict:
        result = current(project, task)
        if not isinstance(result, dict):
            return result
        return _publish_delivery_recovery(project, task, result)

    setattr(execute_task, "_devpilot_delivery_remote_publish", True)
    executor.execute_task = execute_task
    _INSTALLED = True
