#!/usr/bin/env python3
"""Fail fast when a change reintroduces unsafe DevPilot boot/runtime patterns.

This checker intentionally protects architecture, not implementation details. It keeps
pre-authentication and authenticated boot minimal, forces optional UI modules through
the explicit feature loader, and rejects new hidden script loaders/MutationObservers in
ordinary frontend modules.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/main.py"
AUTH = ROOT / "app/static/auth-ui.js"
ACS_LOADER = ROOT / "app/static/acs-loader.js"
FEATURE_LOADER = ROOT / "app/static/feature-loader.js"
AGENTS = ROOT / "AGENTS.md"
VALIDATE_CI = ROOT / "scripts/validate-ci.sh"
TEST_ALL = ROOT / "scripts/test-all.sh"
QUALITY_MATRIX = ROOT / "scripts/critical-quality-matrix.py"
QUALITY_MODULES = ROOT / ".devpilot/quality-modules.json"

EXPECTED_PREAUTH = {"acs-loader.js", "auth-ui.js"}
EXPECTED_CORE = ["app.js", "feature-loader.js"]
EXPECTED_CRITICAL_MODULES = {
    "auth",
    "tasks_worker",
    "game",
    "super_admin",
    "rag",
    "github",
    "linux",
    "cloud_deploy",
    "frontend",
}

DYNAMIC_SCRIPT_PATTERN = re.compile(
    r"(?:createElement\s*\(\s*['\"]script['\"]|"
    r"(?:\.src|src)\s*=\s*[`'\"]\s*/assets/|"
    r"appendChild\s*\(\s*script\s*\)|"
    r"<script\b)",
    re.IGNORECASE,
)
MUTATION_OBSERVER_PATTERN = re.compile(r"\bnew\s+MutationObserver\b")


class PolicyFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PolicyFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def literal_assignment(path: Path, name: str):
    tree = ast.parse(read(path), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        value = node.value
        try:
            return ast.literal_eval(value)
        except (ValueError, TypeError) as exc:
            fail(f"{path.relative_to(ROOT)}:{name} deve permanecer literal/auditável: {exc}")
    fail(f"{path.relative_to(ROOT)} não define {name}")


def check_boot_invariants() -> None:
    preauth = literal_assignment(MAIN, "_PREAUTH_SCRIPT_NAMES")
    core = literal_assignment(MAIN, "_CORE_AUTHENTICATED_SCRIPTS")

    if set(preauth) != EXPECTED_PREAUTH:
        fail(
            "Boot pré-autenticação cresceu. Permitido somente "
            f"{sorted(EXPECTED_PREAUTH)}; encontrado {sorted(preauth)}."
        )
    if list(core) != EXPECTED_CORE:
        fail(
            "Core autenticado deve permanecer mínimo e determinístico: "
            f"{EXPECTED_CORE}; encontrado {list(core)}."
        )

    main_source = read(MAIN)
    loader_block = main_source.split("def _authenticated_script_loader()", 1)[-1].split(
        "@asynccontextmanager", 1
    )[0]
    forbidden_scheduler_tokens = (
        "deferredSources",
        "loadDeferred",
        "requestIdleCallback",
        "data-devpilot-progressive",
    )
    found = [token for token in forbidden_scheduler_tokens if token in loader_block]
    if found:
        fail(f"Scheduler automático de segunda onda voltou ao boot: {', '.join(found)}")


def check_loader_invariants() -> None:
    feature = read(FEATURE_LOADER)
    auth = read(AUTH)
    acs = read(ACS_LOADER)

    required_feature_tokens = (
        "FEATURE_BUNDLES",
        "window.__devpilotLoadFeature = loadFeature",
        "document.addEventListener('click'",
        "devpilot:dashboard-revealed",
    )
    missing = [token for token in required_feature_tokens if token not in feature]
    if missing:
        fail(f"feature-loader perdeu contratos obrigatórios: {', '.join(missing)}")

    if MUTATION_OBSERVER_PATTERN.search(feature):
        fail("feature-loader não pode criar MutationObserver no bootstrap.")
    if "requestIdleCallback" in feature:
        fail("feature-loader não deve iniciar uma segunda onda automática em idle time.")

    auth_contracts = (
        "window.__devpilotAuthReady",
        "devpilot:authenticated-core-ready",
        "devpilot-auth-pending",
        "handoffAuthenticatedRuntime",
    )
    missing = [token for token in auth_contracts if token not in auth]
    if missing:
        fail(f"auth-ui perdeu isolamento/handoff seguro: {', '.join(missing)}")

    if MUTATION_OBSERVER_PATTERN.search(acs):
        fail("ACS loader deve ser somente visual; MutationObserver é proibido.")
    if "loader.style.pointerEvents = 'none'" not in acs:
        fail("ACS loader deve permanecer não bloqueante (pointerEvents = none).")


def check_quality_matrix_contract() -> None:
    if not QUALITY_MATRIX.is_file():
        fail("scripts/critical-quality-matrix.py é obrigatório.")
    if not QUALITY_MODULES.is_file():
        fail(".devpilot/quality-modules.json é obrigatório.")

    try:
        config = json.loads(read(QUALITY_MODULES))
    except json.JSONDecodeError as exc:
        fail(f"quality-modules.json inválido: {exc}")

    names = {
        item.get("name")
        for item in config.get("modules", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    missing = EXPECTED_CRITICAL_MODULES - names
    if config.get("version") != 1:
        fail("quality-modules.json deve permanecer em version=1.")
    if missing:
        fail(f"matriz perdeu módulos críticos: {', '.join(sorted(missing))}")

    validate = read(VALIDATE_CI)
    test_all = read(TEST_ALL)
    if "critical-quality-matrix.py" not in validate:
        fail("validate-ci.sh não valida a matriz de módulos críticos.")
    if "critical-quality-matrix.py" not in test_all:
        fail("test-all.sh não executa a matriz de módulos críticos.")
    if "-m browser_e2e tests" not in test_all:
        fail("test-all.sh deve descobrir todos os browser E2E pelo marker browser_e2e.")


def check_standard_is_wired() -> None:
    agents = read(AGENTS)
    validate = read(VALIDATE_CI)
    if "## Reliability and regression prevention standard" not in agents:
        fail("AGENTS.md não contém o padrão obrigatório de confiabilidade/regressão.")
    if "## Critical module quality matrix" not in agents:
        fail("AGENTS.md não contém a política da matriz de módulos críticos.")
    if "check-engineering-standards.py" not in validate:
        fail("validate-ci.sh não executa o gate de padrões de engenharia.")
    check_quality_matrix_contract()


def resolve_base(explicit: str | None) -> str | None:
    candidates = [explicit, os.getenv("DEVPILOT_POLICY_BASE")]
    for candidate in candidates:
        candidate = (candidate or "").strip()
        if candidate and set(candidate) != {"0"}:
            return candidate

    result = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def changed_added_lines(base: str) -> dict[str, list[str]]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            f"{base}...HEAD",
            "--",
            "app",
            "scripts",
            ".devpilot",
            "AGENTS.md",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        fail(f"Não foi possível calcular diff de política contra {base}: {result.stderr.strip()}")

    by_file: dict[str, list[str]] = {}
    current: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            by_file.setdefault(current, [])
            continue
        if current and line.startswith("+") and not line.startswith("+++"):
            by_file[current].append(line[1:])
    return by_file


def check_changed_frontend(base: str | None) -> None:
    if not base:
        print("[policy] WARN: sem commit base; invariantes globais foram validados, diff incremental ignorado.")
        return

    changed = changed_added_lines(base)
    violations: list[str] = []
    for path, lines in changed.items():
        if not path.startswith("app/static/") or not path.endswith(".js"):
            continue
        if path == "app/static/feature-loader.js":
            continue

        # Scan the complete added text for this file, not each line independently.
        # This intentionally catches formatting such as:
        #   document.createElement(\n  'script'\n)
        # and assignments whose /assets/ value is placed on a later line.
        added_source = "\n".join(lines)
        if DYNAMIC_SCRIPT_PATTERN.search(added_source):
            violations.append(
                f"{path}: loader dinâmico de <script> fora de feature-loader.js (inclusive multilinha)"
            )

        for added in lines:
            if MUTATION_OBSERVER_PATTERN.search(added):
                violations.append(
                    f"{path}: novo MutationObserver em módulo comum: {added.strip()}"
                )

    if violations:
        fail(
            "Mudança viola o padrão de boot sob demanda. Mova carregamento para feature-loader.js "
            "e use eventos explícitos em vez de observadores globais:\n- " + "\n- ".join(violations)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed", action="store_true", help="também valida apenas as linhas adicionadas no diff")
    parser.add_argument("--base", help="commit base para o diff incremental")
    args = parser.parse_args()

    try:
        check_boot_invariants()
        check_loader_invariants()
        check_standard_is_wired()
        if args.changed:
            check_changed_frontend(resolve_base(args.base))
    except PolicyFailure as exc:
        print(f"[policy] ERRO: {exc}", file=sys.stderr)
        return 1

    print(
        "[policy] OK: boot mínimo, features sob demanda, matriz crítica e prevenção de regressão preservados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
