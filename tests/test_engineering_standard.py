from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CI = ROOT / ".github/workflows/ci.yml"
VALIDATE = ROOT / "scripts/validate-ci.sh"
LOCAL_SAFE = ROOT / "scripts/devpilot-local-safe.sh"
POLICY = ROOT / "scripts/check-engineering-standards.py"
STANDARD = ROOT / "docs/ENGINEERING_STANDARD.md"


def test_reliability_standard_is_repository_policy():
    agents = AGENTS.read_text(encoding="utf-8")
    standard = STANDARD.read_text(encoding="utf-8")

    assert "## Reliability and regression prevention standard" in agents
    assert "feature-loader.js" in agents
    assert "DevPilot policy" in agents
    assert "Boot mínimo" in standard
    assert "Runtime local" in standard


def test_ci_has_fast_policy_gate_before_quality():
    workflow = CI.read_text(encoding="utf-8")

    assert "name: DevPilot policy" in workflow
    assert "python scripts/check-engineering-standards.py --changed" in workflow
    assert "needs: policy" in workflow
    assert "fetch-depth: 0" in workflow


def test_full_validation_cannot_skip_policy_or_core_js_syntax():
    validate = VALIDATE.read_text(encoding="utf-8")

    assert 'scripts/check-engineering-standards.py --changed' in validate
    assert "node --check app/static/auth-ui.js" in validate
    assert "node --check app/static/acs-loader.js" in validate
    assert "node --check app/static/feature-loader.js" in validate
    assert "bash -n scripts/devpilot-local-safe.sh" in validate


def test_local_runtime_identifies_service_and_rejects_unknown_port_owner():
    script = LOCAL_SAFE.read_text(encoding="utf-8")

    assert '"service"[[:space:]]*:[[:space:]]*"devpilot"' in script
    assert "assert_port_is_safe" in script
    assert "is_known_devpilot_pid" in script
    assert "recusando iniciar; porta" in script
    assert "RUNTIME: commit=" in script
    assert "check-engineering-standards.py" in script


def test_policy_rejects_hidden_loaders_and_new_global_observers():
    source = POLICY.read_text(encoding="utf-8")

    assert "EXPECTED_CORE = [\"app.js\", \"feature-loader.js\"]" in source
    assert "DYNAMIC_SCRIPT_PATTERN" in source
    assert "MUTATION_OBSERVER_PATTERN" in source
    assert 'path == "app/static/feature-loader.js"' in source
