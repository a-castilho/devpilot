#!/usr/bin/env python3
"""Guarded self-healing loop for failed DevPilot pull-request CI runs.

Repairs are limited to the existing non-main PR branch. The controller never
merges, deploys, force-pushes, changes its standing policy, or weakens CI gates.
Standing authorization is versioned on main and capped by a hard three-attempt
circuit breaker.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / ".artifacts" / "pr-auto-repair" / "report.json"
POLICY_PATH = ".devpilot/pr-auto-repair.json"
MAX_HARD_ATTEMPTS = 3
AUTO_COMMIT_PREFIX = "fix(ci): auto-repair attempt "
LOG_LIMIT = 50_000
VALIDATION_FEEDBACK_LIMIT = 20_000
PROTECTED_PATHS = {
    POLICY_PATH,
    "AGENTS.md",
    "docs/ENGINEERING_STANDARD.md",
    ".github/workflows/ci.yml",
    ".github/workflows/pr-auto-repair.yml",
    "scripts/test-all.sh",
    "scripts/check-engineering-standards.py",
}
SECRET_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[^\s\"']+"),
)


def run(
    args: list[str],
    *,
    check: bool = False,
    timeout: int = 900,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    if check and result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(f"{' '.join(args)}: {message}")
    return result


def required_env(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def write_report(**payload) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redact(value: str) -> str:
    text = str(value or "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def load_main_policy() -> dict:
    result = run(["git", "show", f"origin/main:{POLICY_PATH}"])
    if result.returncode:
        return {"enabled": False, "reason": "policy_not_present_on_main"}
    try:
        policy = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid PR auto-repair policy on main") from exc

    if policy.get("allow_merge") is not False:
        raise RuntimeError("PR auto-repair policy must explicitly keep merge disabled")
    if policy.get("require_open_pull_request") is not True:
        raise RuntimeError("PR auto-repair requires an open pull request")
    if policy.get("require_same_repository") is not True:
        raise RuntimeError("PR auto-repair requires a same-repository branch")
    if policy.get("require_full_validation") is not True:
        raise RuntimeError("PR auto-repair requires full validation before push")
    max_attempts = int(policy.get("max_attempts") or 0)
    if max_attempts < 1 or max_attempts > MAX_HARD_ATTEMPTS:
        raise RuntimeError(f"PR auto-repair max_attempts must be between 1 and {MAX_HARD_ATTEMPTS}")
    return policy


def branch_repair_count(base_ref: str = "origin/main") -> int:
    """Return the highest already-pushed auto-repair attempt number on the branch."""
    merge_base = run(["git", "merge-base", base_ref, "HEAD"], check=True).stdout.strip()
    log = run(["git", "log", "--format=%s", f"{merge_base}..HEAD"], check=True).stdout
    pattern = re.compile(rf"^{re.escape(AUTO_COMMIT_PREFIX)}(?P<attempt>\d+)\b")
    attempts = [int(match.group("attempt")) for line in log.splitlines() if (match := pattern.match(line))]
    return max(attempts, default=0)


def open_pr_number(repository: str, branch: str) -> str:
    result = run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repository,
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number",
            "--jq",
            ".[0].number // empty",
        ]
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "unable to query pull request")
    return result.stdout.strip()


def failed_run_log(run_id: str, repository: str) -> str:
    result = run(["gh", "run", "view", run_id, "--repo", repository, "--log-failed"], timeout=120)
    if result.returncode or not result.stdout.strip():
        result = run(["gh", "run", "view", run_id, "--repo", repository, "--log"], timeout=120)
    text = redact((result.stdout or result.stderr or "CI log unavailable").strip())
    return text[-LOG_LIMIT:]


def changed_paths() -> list[str]:
    result = run(["git", "status", "--porcelain=v1"], check=True)
    paths: list[str] = []
    for raw in result.stdout.splitlines():
        entry = raw[3:].strip()
        if not entry:
            continue
        if " -> " in entry:
            old_path, new_path = entry.split(" -> ", 1)
            paths.extend([old_path.strip(), new_path.strip()])
        else:
            paths.append(entry)
    return list(dict.fromkeys(path for path in paths if path))


def safety_errors(paths: list[str], diff_text: str) -> list[str]:
    errors: list[str] = []
    protected = sorted(set(paths) & PROTECTED_PATHS)
    if protected:
        errors.append("protected paths changed: " + ", ".join(protected))
    for pattern in SECRET_PATTERNS:
        if pattern.search(diff_text):
            errors.append("possible secret detected in repair diff")
            break
    return errors


def reset_worktree() -> None:
    run(["git", "reset", "--hard", "HEAD"])
    run(["git", "clean", "-fd"])


def stage_and_inspect(paths: list[str]) -> tuple[list[str], str, list[str]]:
    run(["git", "add", "-A", "--", *paths], check=True)
    staged_diff = run(["git", "diff", "--cached", "--binary"], check=True).stdout
    staged_paths = run(["git", "diff", "--cached", "--name-only"], check=True).stdout.splitlines()
    violations = safety_errors(staged_paths, staged_diff)
    return staged_paths, staged_diff, violations


def unstage() -> None:
    run(["git", "reset", "--mixed", "HEAD"], check=True)


def codex_repair_prompt(
    *,
    branch: str,
    run_id: str,
    attempt: int,
    max_attempts: int,
    diagnostic: str,
) -> str:
    return f"""PR AUTO REPAIR — tentativa {attempt}/{max_attempts}

Você está na branch de uma Pull Request existente: {branch}.
O CI oficial falhou na execução {run_id}.

OBJETIVO
Diagnostique a causa raiz usando as evidências abaixo e aplique a MENOR correção completa necessária para fazer a implementação correta passar nos gates existentes.

REGRAS OBRIGATÓRIAS
- Leia e obedeça AGENTS.md e docs/ENGINEERING_STANDARD.md antes de editar.
- Não faça commit, push, merge, deploy, alteração de credenciais ou operação destrutiva; o controlador fará commit/push somente após validação.
- Nunca edite .devpilot/pr-auto-repair.json, .github/workflows/ci.yml, .github/workflows/pr-auto-repair.yml, scripts/test-all.sh, scripts/check-engineering-standards.py, AGENTS.md ou docs/ENGINEERING_STANDARD.md.
- Não remova, pule, marque como xfail/skip, afrouxe ou silencie testes/gates para obter verde.
- Testes podem ser corrigidos somente quando o defeito estiver no próprio teste (por exemplo, seletor frágil) e a correção deve aumentar ou preservar a força da verificação.
- Não exponha segredos em arquivos, saída ou comentários.
- Preserve compatibilidade, isolamento e o escopo da PR.
- Execute testes focados úteis durante o diagnóstico. O controlador executará a suíte completa depois.
- Se não houver uma correção segura e determinística, não altere arquivos.

EVIDÊNCIAS DO CI / TENTATIVA ANTERIOR (limitadas e sanitizadas):
-----
{diagnostic[-LOG_LIMIT:]}
-----
"""[:100_000]


def remote_branch_sha(branch: str) -> str:
    result = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], check=True)
    return result.stdout.split()[0] if result.stdout.strip() else ""


def validation_feedback(result: subprocess.CompletedProcess[str], attempt: int) -> str:
    output = redact((result.stdout or "") + "\n" + (result.stderr or ""))[-VALIDATION_FEEDBACK_LIMIT:]
    return (
        f"\n\nA tentativa automática {attempt} produziu uma alteração, mas a validação completa local falhou. "
        "Não repita a mesma correção; use a falha abaixo como nova evidência e corrija a causa raiz:\n"
        f"{output}"
    )


def main() -> int:
    repository = required_env("GITHUB_REPOSITORY")
    branch = required_env("DEVPILOT_FAILED_HEAD_BRANCH")
    run_id = required_env("DEVPILOT_FAILED_RUN_ID")
    failed_head_sha = required_env("DEVPILOT_FAILED_HEAD_SHA")
    expected_repository = str(os.getenv("DEVPILOT_FAILED_HEAD_REPOSITORY") or repository).strip()

    try:
        run(["git", "fetch", "--prune", "origin"], check=True, timeout=180)
        policy = load_main_policy()
        if not policy.get("enabled"):
            write_report(status="skipped", reason=policy.get("reason", "disabled"), branch=branch, run_id=run_id)
            return 0
        if not policy.get("allow_branch_push"):
            write_report(status="skipped", reason="branch_push_not_approved", branch=branch, run_id=run_id)
            return 0
        if expected_repository.lower() != repository.lower():
            write_report(status="blocked", reason="fork_or_repository_mismatch", branch=branch, run_id=run_id)
            return 0
        if branch in {"main", "master"}:
            write_report(status="blocked", reason="protected_branch", branch=branch, run_id=run_id)
            return 0

        pr_number = open_pr_number(repository, branch)
        if not pr_number:
            write_report(status="blocked", reason="no_open_pull_request", branch=branch, run_id=run_id)
            return 0

        max_attempts = min(int(policy["max_attempts"]), MAX_HARD_ATTEMPTS)
        completed_attempts = branch_repair_count()
        if completed_attempts >= max_attempts:
            write_report(
                status="circuit_open",
                reason="max_attempts_reached",
                branch=branch,
                run_id=run_id,
                pr_number=pr_number,
                attempts=completed_attempts,
            )
            return 0

        starting_sha = run(["git", "rev-parse", "HEAD"], check=True).stdout.strip()
        if failed_head_sha != starting_sha:
            write_report(
                status="skipped",
                reason="stale_failed_run",
                branch=branch,
                run_id=run_id,
                failed_head_sha=failed_head_sha,
                current_head_sha=starting_sha,
            )
            return 0
        if remote_branch_sha(branch) != starting_sha:
            write_report(status="blocked", reason="branch_moved_before_repair", branch=branch, run_id=run_id)
            return 0

        diagnostic = failed_run_log(run_id, repository)
        history: list[dict] = []

        for attempt in range(completed_attempts + 1, max_attempts + 1):
            prompt = codex_repair_prompt(
                branch=branch,
                run_id=run_id,
                attempt=attempt,
                max_attempts=max_attempts,
                diagnostic=diagnostic,
            )
            codex = run(["codex", "exec", "--json", prompt], timeout=1800)
            if codex.returncode:
                reset_worktree()
                history.append({"attempt": attempt, "status": "codex_failed"})
                diagnostic += f"\n\nTentativa {attempt}: Codex encerrou com exit code {codex.returncode}."
                continue

            paths = changed_paths()
            if not paths:
                history.append({"attempt": attempt, "status": "no_safe_change"})
                diagnostic += f"\n\nTentativa {attempt}: nenhuma alteração segura foi produzida."
                continue

            staged_paths, _, violations = stage_and_inspect(paths)
            unstage()
            if violations:
                reset_worktree()
                write_report(
                    status="blocked",
                    reason="safety_guard",
                    violations=violations,
                    branch=branch,
                    run_id=run_id,
                    pr_number=pr_number,
                    attempt=attempt,
                    history=history,
                )
                return 1
            if not staged_paths:
                reset_worktree()
                history.append({"attempt": attempt, "status": "empty_diff"})
                continue

            validation_env = os.environ.copy()
            validation_env["DEVPILOT_RUN_BROWSER_E2E"] = "1"
            validation = run(["bash", "scripts/test-all.sh"], timeout=2400, env=validation_env)
            if validation.returncode:
                history.append({"attempt": attempt, "status": "validation_failed"})
                diagnostic += validation_feedback(validation, attempt)
                reset_worktree()
                continue

            if remote_branch_sha(branch) != starting_sha:
                reset_worktree()
                write_report(
                    status="blocked",
                    reason="branch_moved_during_repair",
                    branch=branch,
                    run_id=run_id,
                    pr_number=pr_number,
                    attempt=attempt,
                    history=history,
                )
                return 0

            staged_paths, _, violations = stage_and_inspect(paths)
            if violations:
                reset_worktree()
                raise RuntimeError("staged repair violated safety guard: " + "; ".join(violations))
            if not staged_paths:
                reset_worktree()
                history.append({"attempt": attempt, "status": "diff_disappeared"})
                diagnostic += f"\n\nTentativa {attempt}: o diff desapareceu após a validação."
                continue

            run(["git", "config", "user.name", "DevPilot Auto Repair"], check=True)
            run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
            message = f"{AUTO_COMMIT_PREFIX}{attempt} for run {run_id}"
            run(["git", "commit", "-m", message], check=True)
            repaired_sha = run(["git", "rev-parse", "HEAD"], check=True).stdout.strip()
            push = run(["git", "push", "origin", f"HEAD:{branch}"], timeout=180)
            if push.returncode:
                raise RuntimeError(push.stderr.strip() or "repair push failed")

            dispatch = run(
                ["gh", "workflow", "run", "ci.yml", "--repo", repository, "--ref", branch],
                timeout=120,
            )
            if dispatch.returncode:
                raise RuntimeError(dispatch.stderr.strip() or "unable to dispatch CI revalidation")

            history.append({"attempt": attempt, "status": "pushed"})
            write_report(
                status="pushed",
                branch=branch,
                run_id=run_id,
                pr_number=pr_number,
                attempt=attempt,
                repaired_sha=repaired_sha,
                changed_paths=staged_paths,
                validation="passed",
                revalidation="dispatched",
                history=history,
            )
            print(f"PR auto-repair pushed {repaired_sha[:8]} to {branch}; CI revalidation dispatched.")
            return 0

        reset_worktree()
        write_report(
            status="circuit_open",
            reason="attempts_exhausted_without_validated_repair",
            branch=branch,
            run_id=run_id,
            pr_number=pr_number,
            attempts=max_attempts,
            history=history,
        )
        return 1
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        try:
            reset_worktree()
        except Exception:
            pass
        write_report(
            status="failed",
            reason="controller_error",
            branch=branch,
            run_id=run_id,
            error=redact(str(error))[:2000],
        )
        print(f"PR auto-repair error: {redact(str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
