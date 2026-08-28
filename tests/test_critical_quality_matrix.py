from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/critical-quality-matrix.py"
CONFIG = ROOT / ".devpilot/quality-modules.json"


def load_matrix_module():
    spec = importlib.util.spec_from_file_location("devpilot_critical_quality_matrix", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quality_matrix_declares_all_critical_domains():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    assert {
        "auth",
        "tasks_worker",
        "game",
        "super_admin",
        "rag",
        "github",
        "linux",
        "cloud_deploy",
        "frontend",
    } <= set(modules)
    assert modules["auth"]["active"] is True
    assert modules["game"]["active"] is True
    assert modules["frontend"]["active"] is True
    assert modules["rag"]["active"] is False


def test_game_change_selects_game_and_frontend_contracts():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/static/build-game.js"],
    )

    assert structural is False
    assert "game" in selected
    assert "frontend" in selected


def test_auth_change_selects_auth_contract():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/auth_routes.py"],
    )

    assert structural is False
    assert "auth" in selected


def test_structural_change_selects_every_active_module():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/main.py"],
    )

    expected = sorted(name for name, module in modules.items() if module["active"])
    assert structural is True
    assert selected == expected
    assert "rag" not in selected


def test_guarded_critical_path_without_owner_is_rejected():
    matrix = load_matrix_module()
    config = {
        "structural_paths": [],
        "guard_patterns": ["app/critical/**"],
    }
    modules = {
        "owned": {
            "active": True,
            "source": ["app/owned/**"],
            "tests": ["tests/test_owned.py"],
            "browser_tests": [],
        }
    }

    with pytest.raises(matrix.MatrixFailure, match="sem contrato de qualidade"):
        matrix.select_modules(config, modules, ["app/critical/new_feature.py"])


def test_report_contains_focused_and_browser_contracts():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/static/build-game.js"],
    )
    report = matrix.build_report(
        config,
        modules,
        ["app/static/build-game.js"],
        selected,
        structural,
    )

    assert "tests/test_game_browser_e2e.py" in report["browser_e2e_contracts"]
    assert "tests/test_build_game_ui.py" in report["focused_tests"]
    assert "tests/test_frontend_runtime_circuit_breaker.py" in report["focused_tests"]
