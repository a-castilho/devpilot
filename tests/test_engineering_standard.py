import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CI = ROOT / ".github/workflows/ci.yml"
WORKFLOWS = ROOT / ".github/workflows"
VALIDATE = ROOT / "scripts/validate-ci.sh"
TEST_ALL = ROOT / "scripts/test-all.sh"
LOCAL_SAFE = ROOT / "scripts/devpilot-local-safe.sh"
SELF_HOSTED_SETUP = ROOT / "scripts/setup-github-self-hosted-runner.sh"
POLICY = ROOT / "scripts/check-engineering-standards.py"
QUALITY_MATRIX = ROOT / "scripts/critical-quality-matrix.py"
QUALITY_CONFIG = ROOT / ".devpilot/quality-modules.json"
STANDARD = ROOT / "docs/ENGINEERING_STANDARD.md"


def test_reliability_standard_is_repository_policy():
    agents = AGENTS.read_text(encoding="utf-8")
    standard = STANDARD.read_text(encoding="utf-8")

    assert "## Reliability and regression prevention standard" in agents
    assert "## Critical module quality matrix" in agents
    assert "feature-loader.js" in agents
    assert "DevPilot policy" in agents
    assert "Boot mínimo" in standard
    assert "Matriz de qualidade por módulo crítico" in standard
    assert "Runtime local" in standard


def test_ci_has_fast_policy_gate_before_quality():
    workflow = CI.read_text(encoding="utf-8")

    assert "name: DevPilot policy" in workflow
    assert "python scripts/check-engineering-standards.py --changed" in workflow
    assert "needs: policy" in workflow
    assert "fetch-depth: 0" in workflow
    assert 'DEVPILOT_RUN_CRITICAL_MATRIX: "1"' in workflow
    assert 'DEVPILOT_RUN_BROWSER_E2E: "1"' in workflow


def test_full_validation_cannot_skip_policy_or_core_js_syntax():
    validate = VALIDATE.read_text(encoding="utf-8")

    assert 'scripts/check-engineering-standards.py --changed' in validate
    assert "scripts/critical-quality-matrix.py" in validate
    assert "node --check app/static/auth-ui.js" in validate
    assert "node --check app/static/acs-loader.js" in validate
    assert "node --check app/static/feature-loader.js" in validate
    assert "bash -n scripts/devpilot-local-safe.sh" in validate


def test_critical_quality_matrix_is_wired_without_replacing_full_suite():
    config = json.loads(QUALITY_CONFIG.read_text(encoding="utf-8"))
    matrix = QUALITY_MATRIX.read_text(encoding="utf-8")
    test_all = TEST_ALL.read_text(encoding="utf-8")

    names = {module["name"] for module in config["modules"]}
    assert config["version"] == 1
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
    } <= names
    assert "guard_patterns" in config
    assert "arquivo crítico sem contrato de qualidade" in matrix
    assert "run_focused_tests" in matrix
    assert "critical-quality-matrix.py" in test_all
    assert 'pytest -q -m "not browser_e2e"' in test_all
    assert "-name '*_browser_e2e.py'" in test_all
    assert '"${browser_e2e_files[@]}"' in test_all
    assert "-m browser_e2e tests" not in test_all


def test_local_runtime_identifies_service_and_rejects_unknown_port_owner():
    script = LOCAL_SAFE.read_text(encoding="utf-8")

    assert '"service"[[:space:]]*:[[:space:]]*"devpilot"' in script
    assert "assert_port_is_safe" in script
    assert "is_known_devpilot_pid" in script
    assert "require_port_inspector" in script
    assert "lsof, fuser ou ss" in script
    assert "possui listener, mas o PID não pôde ser identificado" in script
    assert "recusando iniciar; porta" in script
    assert "RUNTIME: commit=" in script
    assert "check-engineering-standards.py" in script


def test_local_runtime_restores_previous_revision_on_shutdown_timeout():
    script = LOCAL_SAFE.read_text(encoding="utf-8")

    assert "restore_after_shutdown_timeout" in script
    assert 'git reset --hard "$target_sha"' in script
    assert 'restore_after_shutdown_timeout "$BEFORE_SHA"' in script
    assert "RECUPERAÇÃO OK" in script


def test_local_runtime_port_wait_is_safe_under_errexit():
    script = LOCAL_SAFE.read_text(encoding="utf-8")
    wait_block = script.split("wait_for_port_free()", 1)[1].split("wait_for_health()", 1)[0]

    assert "if port_has_listener; then state=0; else state=$?; fi" in wait_block
    assert "port_has_listener\n    state=$?" not in wait_block


def test_policy_rejects_hidden_loaders_and_new_global_observers():
    source = POLICY.read_text(encoding="utf-8")

    assert "EXPECTED_CORE = [\"app.js\", \"feature-loader.js\"]" in source
    assert "EXPECTED_CRITICAL_MODULES" in source
    assert "DYNAMIC_SCRIPT_PATTERN" in source
    assert "MUTATION_OBSERVER_PATTERN" in source
    assert 'path == "app/static/feature-loader.js"' in source
    assert 'added_source = "\\n".join(lines)' in source
    assert "DYNAMIC_SCRIPT_PATTERN.search(added_source)" in source


def test_resource_intensive_workflows_keep_self_hosted_fallback():
    critical = (
        "ci.yml",
        "compromisso-geral.yml",
        "deploy-homolog.yml",
        "issue-documentation.yml",
        "project-report.yml",
        "vercel-cli-deploy.yml",
    )
    for name in critical:
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "vars.DEVPILOT_RUNNER || 'ubuntu-latest'" in workflow, name
        assert "runs-on: ubuntu-latest" not in workflow, name


def test_review_documentation_cannot_starve_quality_runner_or_churn_on_every_push():
    workflow = (WORKFLOWS / "review-documentation.yml").read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in workflow
    assert "DEVPILOT_DOCS_RUNNER" not in workflow
    assert "types: [opened, edited, reopened, ready_for_review, closed]" in workflow
    assert "synchronize" not in workflow


def test_review_reports_do_not_trigger_full_main_ci():
    workflow = CI.read_text(encoding="utf-8")

    assert "paths-ignore:" in workflow
    assert '"docs/reviews/**"' in workflow


def test_self_hosted_runner_bootstrap_is_private_and_does_not_echo_token():
    source = SELF_HOSTED_SETUP.read_text(encoding="utf-8")

    assert '[[ "$visibility" == "PRIVATE" ]]' in source
    assert "registration-token" in source
    assert "gh variable set DEVPILOT_RUNNER" in source
    assert "devpilot-ci" in source
    assert "set -x" not in source
