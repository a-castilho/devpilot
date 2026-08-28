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
    assert modules["tasks_worker"]["active"] is True
    assert modules["game"]["active"] is True
    assert modules["super_admin"]["active"] is True
    assert modules["frontend"]["active"] is True
    assert modules["rag"]["activate_when_source_exists"] is True
    assert modules["rag"]["browser_required"] is True


def test_primary_critical_domains_have_browser_contracts():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    shared = "tests/test_critical_flows_browser_e2e.py"
    assert modules["auth"]["browser_required"] is True
    assert shared in modules["auth"]["browser_files"]
    assert modules["tasks_worker"]["browser_required"] is True
    assert shared in modules["tasks_worker"]["browser_files"]
    assert modules["super_admin"]["browser_required"] is True
    assert shared in modules["super_admin"]["browser_files"]
    assert "tests/test_game_browser_e2e.py" in modules["game"]["browser_files"]
    assert "tests/test_rag_browser_e2e.py" in modules["rag"]["browser_files"]


def test_browser_contract_requires_browser_marker(tmp_path, monkeypatch):
    matrix = load_matrix_module()
    app_dir = tmp_path / "app"
    tests_dir = tmp_path / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()
    (app_dir / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests_dir / "test_demo.py").write_text("def test_demo(): assert True\n", encoding="utf-8")
    browser = tests_dir / "test_demo_browser_e2e.py"
    browser.write_text("import pytest\n\ndef test_browser(): assert True\n", encoding="utf-8")
    monkeypatch.setattr(matrix, "ROOT", tmp_path)

    config = {
        "version": 1,
        "structural_paths": [],
        "guard_patterns": [],
        "modules": [
            {
                "name": "demo",
                "source": ["app/demo.py"],
                "tests": ["tests/test_demo.py"],
                "browser_tests": ["tests/test_demo_browser_e2e.py"],
                "browser_required": True,
            }
        ],
    }

    with pytest.raises(matrix.MatrixFailure, match="sem marker browser_e2e"):
        matrix.validate_config(config)

    browser.write_text(
        "import pytest\n\npytestmark = pytest.mark.browser_e2e\n\ndef test_browser(): assert True\n",
        encoding="utf-8",
    )
    modules = matrix.validate_config(config)
    assert modules["demo"]["browser_files"] == ["tests/test_demo_browser_e2e.py"]


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


def test_task_change_selects_task_worker_contract():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/task_run_routes.py"],
    )

    assert structural is False
    assert "tasks_worker" in selected


def test_super_admin_change_selects_admin_contract():
    matrix = load_matrix_module()
    config = matrix.load_config(CONFIG)
    modules = matrix.validate_config(config)

    selected, structural = matrix.select_modules(
        config,
        modules,
        ["app/super_admin_voice_routes.py"],
    )

    assert structural is False
    assert "super_admin" in selected


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
    assert ("rag" in selected) is modules["rag"]["active"]


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


def test_structural_change_cannot_bypass_guarded_ownership():
    matrix = load_matrix_module()
    config = {
        "structural_paths": [".devpilot/quality-modules.json"],
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
        matrix.select_modules(
            config,
            modules,
            [".devpilot/quality-modules.json", "app/critical/new_feature.py"],
        )


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
    assert "tests/test_critical_flows_browser_e2e.py" in report["browser_e2e_contracts"]
    assert "tests/test_build_game_ui.py" in report["focused_tests"]
    assert "tests/test_frontend_runtime_circuit_breaker.py" in report["focused_tests"]
