from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


DEFAULT_INCLUDE = "git,code,tests,deploy,security,docs,product"


def _run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _project_root(value: str) -> Path:
    if value == "current":
        root_text = _run_git(Path.cwd(), "rev-parse", "--show-toplevel")
        return Path(root_text).resolve() if root_text else Path.cwd().resolve()
    return Path(value).expanduser().resolve()


def _count_files(root: Path, patterns: tuple[str, ...]) -> int:
    count = 0
    blocked = {".git", ".venv", "venv", "node_modules", "vendor", "dist", "build", "__pycache__"}
    for pattern in patterns:
        for path in root.rglob(pattern):
            if any(part in blocked for part in path.parts):
                continue
            if path.is_file():
                count += 1
    return count


def _exists_any(root: Path, candidates: tuple[str, ...]) -> bool:
    return any((root / candidate).exists() for candidate in candidates)


def _git_signals(root: Path) -> dict[str, Any]:
    branch = _run_git(root, "branch", "--show-current")
    commits_text = _run_git(root, "rev-list", "--count", "HEAD")
    recent = _run_git(root, "log", "-n", "8", "--pretty=format:%h|%ad|%s", "--date=short")
    status = _run_git(root, "status", "--porcelain")
    remotes = _run_git(root, "remote", "-v")
    try:
        commit_count = int(commits_text or "0")
    except ValueError:
        commit_count = 0
    return {
        "branch": branch or None,
        "commit_count": commit_count,
        "dirty": bool(status),
        "changed_files": len(status.splitlines()) if status else 0,
        "has_remote": bool(remotes),
        "recent_commits": recent.splitlines() if recent else [],
    }


def _collect_signals(root: Path, include: set[str]) -> dict[str, Any]:
    signals: dict[str, Any] = {}
    if "git" in include:
        signals["git"] = _git_signals(root)
    if "code" in include:
        signals["code"] = {
            "python_files": _count_files(root, ("*.py",)),
            "javascript_files": _count_files(root, ("*.js", "*.mjs", "*.cjs")),
            "typescript_files": _count_files(root, ("*.ts", "*.tsx")),
            "php_files": _count_files(root, ("*.php",)),
        }
    if "tests" in include:
        signals["tests"] = {
            "test_files": _count_files(root, ("test_*.py", "*_test.py", "*.spec.js", "*.test.js", "*.spec.ts", "*.test.ts")),
            "has_test_config": _exists_any(root, ("pytest.ini", "pyproject.toml", "jest.config.js", "vitest.config.ts")),
        }
    if "deploy" in include:
        signals["deploy"] = {
            "docker": _exists_any(root, ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")),
            "github_actions": (root / ".github" / "workflows").exists(),
            "render": (root / "render.yaml").exists(),
            "vercel": (root / "vercel.json").exists(),
        }
    if "security" in include:
        signals["security"] = {
            "gitignore": (root / ".gitignore").exists(),
            "env_example": _exists_any(root, (".env.example", ".env.sample")),
            "agents_policy": (root / "AGENTS.md").exists(),
            "security_module": _exists_any(root, ("app/security.py", "security.py")),
        }
    if "docs" in include:
        signals["docs"] = {
            "readme": _exists_any(root, ("README.md", "README.rst")),
            "docs_dir": (root / "docs").exists(),
            "agents": (root / "AGENTS.md").exists(),
        }
    if "product" in include:
        signals["product"] = {
            "has_ui": _exists_any(root, ("app/static/index.html", "index.html", "src")),
            "has_api": _exists_any(root, ("app/main.py", "main.py", "server.py")),
            "has_project_metadata": _exists_any(root, ("pyproject.toml", "package.json", "composer.json")),
        }
    return signals


def _score(signals: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    points = 0
    maximum = 0
    strengths: list[str] = []
    risks: list[str] = []

    git = signals.get("git")
    if git:
        maximum += 20
        if git["has_remote"]:
            points += 6
            strengths.append("Repositório Git remoto configurado")
        else:
            risks.append("Projeto sem remoto Git detectado")
        if git["commit_count"] >= 10:
            points += 8
            strengths.append("Histórico Git consistente")
        elif git["commit_count"]:
            points += 4
            risks.append("Histórico Git ainda curto")
        if not git["dirty"]:
            points += 6
        else:
            points += 2
            risks.append(f"Worktree possui {git['changed_files']} alteração(ões) não consolidadas")

    tests = signals.get("tests")
    if tests:
        maximum += 20
        count = tests["test_files"]
        if count >= 15:
            points += 20
            strengths.append(f"Boa base de testes detectada ({count} arquivos)")
        elif count >= 5:
            points += 14
            strengths.append(f"Base de testes presente ({count} arquivos)")
        elif count:
            points += 7
            risks.append("Cobertura de testes aparenta ser pequena")
        else:
            risks.append("Nenhum arquivo de teste detectado")

    deploy = signals.get("deploy")
    if deploy:
        maximum += 15
        enabled = sum(bool(value) for value in deploy.values())
        points += min(15, enabled * 4)
        if enabled >= 2:
            strengths.append("Infraestrutura de entrega/deploy presente")
        else:
            risks.append("Automação de deploy limitada")

    security = signals.get("security")
    if security:
        maximum += 15
        enabled = sum(bool(value) for value in security.values())
        points += round(15 * enabled / max(1, len(security)))
        if enabled >= 3:
            strengths.append("Controles básicos de segurança e governança presentes")
        else:
            risks.append("Controles de segurança/governança incompletos")

    docs = signals.get("docs")
    if docs:
        maximum += 10
        enabled = sum(bool(value) for value in docs.values())
        points += round(10 * enabled / max(1, len(docs)))
        if enabled >= 2:
            strengths.append("Documentação estrutural disponível")
        else:
            risks.append("Documentação insuficiente")

    product = signals.get("product")
    if product:
        maximum += 10
        enabled = sum(bool(value) for value in product.values())
        points += round(10 * enabled / max(1, len(product)))
        if enabled == len(product):
            strengths.append("Sinais de produto completo: UI, API e metadados")
        else:
            risks.append("Produto ainda possui camadas estruturais ausentes")

    code = signals.get("code")
    if code:
        maximum += 10
        total = sum(code.values())
        if total >= 30:
            points += 10
            strengths.append("Base de código substancial")
        elif total:
            points += 6
        else:
            risks.append("Nenhum código-fonte relevante detectado")

    score = round(100 * points / maximum) if maximum else 0
    return max(0, min(100, score)), strengths, risks


def _recommendations(score: int, signals: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    tests = signals.get("tests", {})
    if tests and tests.get("test_files", 0) < 5:
        recs.append("Aumentar testes automatizados dos fluxos críticos")
    deploy = signals.get("deploy", {})
    if deploy and not deploy.get("github_actions"):
        recs.append("Adicionar CI obrigatório antes de merge/deploy")
    security = signals.get("security", {})
    if security and not security.get("security_module"):
        recs.append("Centralizar controles de autenticação/autorização e validações de segurança")
    git = signals.get("git", {})
    if git and git.get("dirty"):
        recs.append("Consolidar ou descartar alterações locais antes da próxima avaliação")
    if score < 70:
        recs.append("Priorizar riscos de engenharia antes de ampliar novas funcionalidades")
    elif score < 90:
        recs.append("Atacar os dois maiores riscos para elevar o Guru Score acima de 90")
    else:
        recs.append("Manter regressão, segurança e deploy como gates contínuos")
    return recs[:5]


def _ollama_summary(root: Path, report: dict[str, Any]) -> str | None:
    if os.getenv("DEVPILOT_GURU_AI", "1").strip().lower() in {"0", "false", "off", "no"}:
        return None
    base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("DEVPILOT_GURU_MODEL", "tinyllama")
    compact = json.dumps(
        {
            "project": root.name,
            "score": report["score"],
            "strengths": report["strengths"],
            "risks": report["risks"],
            "recommendations": report["recommendations"],
        },
        ensure_ascii=False,
    )
    prompt = (
        "Você é O Guru do DevPilot. Resuma em português, de forma técnica e objetiva, "
        "a probabilidade de sucesso do projeto. Não invente fatos. Use no máximo 6 frases.\n"
        + compact
    )
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=20,
        )
        response.raise_for_status()
        text = str(response.json().get("response") or "").strip()
        return text or None
    except Exception:
        return None


def _save_history(root: Path, report: dict[str, Any]) -> Path:
    target_dir = root / ".devpilot"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "guru-history.jsonl"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")
    return target


def _sync_game(root: Path, report: dict[str, Any]) -> Path:
    score = report["score"]
    rewards = {
        "stars": max(1, score // 20),
        "moons": 1 if score >= 70 else 0,
        "swords": 1 if score >= 85 else 0,
        "can_advance": score >= 70,
    }
    payload = {
        "updated_at": report["created_at"],
        "guru_score": score,
        "rewards": rewards,
    }
    target_dir = root / ".devpilot"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "guru-game.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["game"] = payload
    return target


def guru_analyze(args: argparse.Namespace) -> int:
    root = _project_root(args.project)
    if not root.exists():
        print(f"Projeto não encontrado: {root}", file=sys.stderr)
        return 2

    include = {item.strip().lower() for item in args.include.split(",") if item.strip()}
    signals = _collect_signals(root, include)
    score, strengths, risks = _score(signals)
    report: dict[str, Any] = {
        "guru": "O Guru",
        "project": root.name,
        "project_path": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "probability": score,
        "status": "alta" if score >= 80 else "moderada" if score >= 60 else "baixa",
        "strengths": strengths,
        "risks": risks,
        "recommendations": _recommendations(score, signals),
        "signals": signals,
    }

    if args.game_sync:
        game_file = _sync_game(root, report)
        report["game_file"] = str(game_file)
    if args.save_history:
        history_file = _save_history(root, report)
        report["history_file"] = str(history_file)

    ai_summary = _ollama_summary(root, report)
    report["ai_summary"] = ai_summary
    report["ai_used"] = bool(ai_summary)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devpilot", description="DevPilot command line interface")
    subparsers = parser.add_subparsers(dest="command")

    guru = subparsers.add_parser("guru", help="O Guru: avaliação técnica do projeto")
    guru_sub = guru.add_subparsers(dest="guru_command")
    analyze = guru_sub.add_parser("analyze", help="Analisa a probabilidade técnica de sucesso")
    analyze.add_argument("--project", default="current", help="current ou caminho do projeto")
    analyze.add_argument("--include", default=DEFAULT_INCLUDE, help="Sinais separados por vírgula")
    analyze.add_argument("--save-history", action="store_true", help="Salva histórico em .devpilot")
    analyze.add_argument("--game-sync", action="store_true", help="Atualiza snapshot do jogo em .devpilot")
    analyze.set_defaults(func=guru_analyze)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
