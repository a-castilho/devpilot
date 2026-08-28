#!/usr/bin/env python3
"""Select and run quality gates for DevPilot critical modules.

The full test suite remains mandatory. This matrix adds an earlier, module-aware gate:
changes in critical areas immediately run the tests declared for those areas and fail if
a guarded source area has no test contract.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".devpilot/quality-modules.json"
BROWSER_MARKER = "pytest.mark.browser_e2e"
BROWSER_FILE_SUFFIX = "_browser_e2e.py"


class MatrixFailure(RuntimeError):
    pass


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def expand_files(patterns: list[str]) -> list[str]:
    """Expand patterns against real files, including recursive ** contracts."""
    found: set[str] = set()
    for candidate in ROOT.rglob("*"):
        if not candidate.is_file() or ".git" in candidate.parts:
            continue
        relative = candidate.relative_to(ROOT).as_posix()
        if path_matches(relative, patterns):
            found.add(relative)
    return sorted(found)


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixFailure(f"matriz não encontrada: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixFailure(f"matriz JSON inválida: {exc}") from exc
    if not isinstance(data, dict):
        raise MatrixFailure("matriz deve ser um objeto JSON")
    return data


def validate_browser_contract_file(module_name: str, relative_path: str) -> None:
    """Ensure a declared browser contract is collected by the dedicated E2E gate."""
    if not relative_path.endswith(BROWSER_FILE_SUFFIX):
        raise MatrixFailure(
            f"{module_name}: browser E2E fora do padrão *{BROWSER_FILE_SUFFIX}: {relative_path}"
        )
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    if BROWSER_MARKER not in source:
        raise MatrixFailure(
            f"{module_name}: browser E2E sem marker browser_e2e: {relative_path}"
        )


def validate_config(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if config.get("version") != 1:
        raise MatrixFailure("quality-modules.json deve usar version=1")

    structural = config.get("structural_paths")
    guards = config.get("guard_patterns")
    modules = config.get("modules")
    if not isinstance(structural, list) or not all(isinstance(item, str) for item in structural):
        raise MatrixFailure("structural_paths deve ser uma lista de padrões")
    if not isinstance(guards, list) or not all(isinstance(item, str) for item in guards):
        raise MatrixFailure("guard_patterns deve ser uma lista de padrões")
    if not isinstance(modules, list) or not modules:
        raise MatrixFailure("modules deve declarar ao menos um módulo crítico")

    by_name: dict[str, dict[str, Any]] = {}
    for module in modules:
        if not isinstance(module, dict):
            raise MatrixFailure("cada módulo deve ser um objeto")
        name = module.get("name")
        source = module.get("source")
        tests = module.get("tests")
        browser_tests = module.get("browser_tests", [])
        optional = bool(module.get("activate_when_source_exists", False))
        if not isinstance(name, str) or not name.strip():
            raise MatrixFailure("módulo sem name válido")
        if name in by_name:
            raise MatrixFailure(f"módulo duplicado: {name}")
        if not isinstance(source, list) or not source or not all(isinstance(item, str) for item in source):
            raise MatrixFailure(f"{name}: source deve possuir padrões")
        if not isinstance(tests, list) or not tests or not all(isinstance(item, str) for item in tests):
            raise MatrixFailure(f"{name}: tests deve possuir padrões")
        if not isinstance(browser_tests, list) or not all(isinstance(item, str) for item in browser_tests):
            raise MatrixFailure(f"{name}: browser_tests deve ser uma lista")

        source_files = expand_files(source)
        test_files = expand_files(tests)
        browser_files = expand_files(browser_tests)
        active = bool(source_files)
        if not active and not optional:
            raise MatrixFailure(f"{name}: nenhum source atual corresponde à configuração")
        if active and not test_files:
            raise MatrixFailure(f"{name}: módulo ativo sem testes correspondentes")
        if module.get("browser_required") and active and not browser_files:
            raise MatrixFailure(f"{name}: browser_required sem E2E correspondente")
        for browser_file in browser_files:
            validate_browser_contract_file(name, browser_file)

        enriched = dict(module)
        enriched["active"] = active
        enriched["source_files"] = source_files
        enriched["test_files"] = test_files
        enriched["browser_files"] = browser_files
        by_name[name] = enriched

    return by_name


def guarded_path_owners(
    config: dict[str, Any],
    modules: dict[str, dict[str, Any]],
    path: str,
) -> list[str]:
    if not path_matches(path, config["guard_patterns"]):
        return []
    return [
        name
        for name, module in modules.items()
        if path_matches(path, list(module["source"]))
    ]


def validate_guarded_ownership(
    config: dict[str, Any],
    modules: dict[str, dict[str, Any]],
    changed_paths: list[str],
) -> None:
    """Reject unowned critical paths even when the same diff is structural."""
    for path in changed_paths:
        if not path_matches(path, config["guard_patterns"]):
            continue
        if guarded_path_owners(config, modules, path):
            continue
        raise MatrixFailure(
            f"arquivo crítico sem contrato de qualidade: {path}; adicione-o a quality-modules.json"
        )


def select_modules(
    config: dict[str, Any],
    modules: dict[str, dict[str, Any]],
    changed_paths: list[str],
) -> tuple[list[str], bool]:
    # Ownership is an invariant, not a selection optimization. Validate it before
    # the structural fast path so editing the matrix itself cannot bypass the guard.
    validate_guarded_ownership(config, modules, changed_paths)

    structural = any(path_matches(path, config["structural_paths"]) for path in changed_paths)
    if structural:
        selected = sorted(name for name, module in modules.items() if module["active"])
        return selected, True

    selected: set[str] = set()
    for path in changed_paths:
        for name, module in modules.items():
            watched = list(module["source"]) + list(module["tests"]) + list(module.get("browser_tests", []))
            if path_matches(path, watched):
                selected.add(name)

    return sorted(selected), False


def resolve_base(explicit: str | None) -> str | None:
    for candidate in (explicit, os.getenv("DEVPILOT_POLICY_BASE")):
        value = (candidate or "").strip()
        if value and set(value) != {"0"}:
            return value
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def changed_paths(base: str | None) -> list[str]:
    if not base:
        return []
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise MatrixFailure(f"não foi possível calcular diff contra {base}: {result.stderr.strip()}")
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def build_report(
    config: dict[str, Any],
    modules: dict[str, dict[str, Any]],
    changed: list[str],
    selected: list[str],
    structural: bool,
) -> dict[str, Any]:
    tests: set[str] = set()
    browser: set[str] = set()
    for name in selected:
        module = modules[name]
        if not module["active"]:
            continue
        tests.update(module["test_files"])
        browser.update(module["browser_files"])
    return {
        "version": config["version"],
        "changed_paths": changed,
        "structural_change": structural,
        "selected_modules": selected,
        "focused_tests": sorted(tests),
        "browser_e2e_contracts": sorted(browser),
    }


def write_report(report: dict[str, Any], target: str | None) -> None:
    if not target:
        return
    path = ROOT / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_focused_tests(test_files: list[str]) -> int:
    if not test_files:
        print("[matrix] nenhum módulo crítico afetado; gate focado não precisa executar pytest.")
        return 0
    command = [sys.executable, "-m", "pytest", "-q", "-m", "not browser_e2e", *test_files]
    print("[matrix] executando:", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="commit base usado para detectar arquivos alterados")
    parser.add_argument("--all", action="store_true", help="seleciona todos os módulos ativos")
    parser.add_argument("--run", action="store_true", help="executa pytest focado para módulos selecionados")
    parser.add_argument("--report", help="caminho relativo para gravar o relatório JSON")
    args = parser.parse_args()

    try:
        config = load_config()
        modules = validate_config(config)
        if args.all:
            changed = []
            selected = sorted(name for name, module in modules.items() if module["active"])
            structural = True
        else:
            base = resolve_base(args.base)
            changed = changed_paths(base)
            if base is None:
                selected = sorted(name for name, module in modules.items() if module["active"])
                structural = True
                print("[matrix] WARN: sem base Git; validando todos os módulos ativos.")
            else:
                selected, structural = select_modules(config, modules, changed)

        report = build_report(config, modules, changed, selected, structural)
        write_report(report, args.report)

        active = sorted(name for name, module in modules.items() if module["active"])
        inactive = sorted(name for name, module in modules.items() if not module["active"])
        print(f"[matrix] módulos ativos: {', '.join(active) or 'nenhum'}")
        if inactive:
            print(f"[matrix] módulos aguardando source: {', '.join(inactive)}")
        print(f"[matrix] mudança estrutural: {'sim' if structural else 'não'}")
        print(f"[matrix] módulos selecionados: {', '.join(selected) or 'nenhum'}")
        print(f"[matrix] testes focados: {len(report['focused_tests'])}")
        print(f"[matrix] contratos browser E2E: {len(report['browser_e2e_contracts'])}")

        if args.run:
            return run_focused_tests(report["focused_tests"])
        return 0
    except MatrixFailure as exc:
        print(f"[matrix] ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
