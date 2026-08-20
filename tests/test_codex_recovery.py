from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from app.models import Project, Task
from app.services import executor


USAGE_LIMIT_JSONL = "\n".join(
    [
        '{"type":"thread.started","thread_id":"test"}',
        '{"type":"error","message":"You have hit your usage limit. Purchase more credits or try again at 12:41 AM."}',
        '{"type":"turn.failed","error":{"message":"You have hit your usage limit."}}',
    ]
)


def project() -> Project:
    return Project(
        id="project-1",
        workspace_id="workspace-1",
        name="RegulaAI",
        slug="regulaai",
        description="",
        repository_url="https://github.com/a-castilho/regulaai.git",
        default_branch="main",
        agents_md="",
        codex_config="{}",
    )


def task() -> Task:
    return Task(
        id="task-12345678",
        workspace_id="workspace-1",
        project_id="project-1",
        title="Implementar ajuste",
        prompt="Implemente a mudança solicitada com testes.",
        source="dashboard",
        priority=50,
        requires_approval=False,
    )


def settings():
    return SimpleNamespace(
        execution_enabled=True,
        task_executor="auto",
        local_readonly_enabled=True,
        codex_api_fallback_enabled=True,
        codex_api_fallback_connection_label="",
    )


def completed(args, code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=stderr)


def test_usage_limit_is_classified_as_blocked_and_retryable():
    failure = executor._classify_codex_failure(USAGE_LIMIT_JSONL, "")

    assert failure["code"] == "usage_limit"
    assert failure["blocked"] is True
    assert failure["retryable"] is True
    assert "Limite do Codex" in str(failure["message"])


def test_usage_limit_without_saved_api_key_preserves_task_as_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(executor, "get_settings", settings)
    monkeypatch.setattr(executor, "ensure_repository", lambda _: tmp_path)
    monkeypatch.setattr(executor, "_saved_openai_api_key", lambda *_args, **_kwargs: "")

    def fake_run(args, cwd=None, timeout=900, env_overrides=None):
        if args[:2] == ["git", "switch"]:
            return completed(args)
        if args[:2] == ["git", "status"]:
            return completed(args, stdout="")
        if args[:3] == ["codex", "exec", "--json"]:
            return completed(args, code=1, stdout=USAGE_LIMIT_JSONL)
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(executor, "run", fake_run)
    result = executor.execute_task(project(), task())

    assert result["blocked"] is True
    assert result["failure_code"] == "usage_limit"
    assert result["provider"] == "chatgpt-codex"
    assert result["auth_mode"] == "chatgpt_session"
    assert result["fallback_used"] is False
    assert len(result["attempts"]) == 1
    assert "Modelos de IA" in result["suggested_action"]


def test_usage_limit_retries_once_with_isolated_openai_api_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(executor, "get_settings", settings)
    monkeypatch.setattr(executor, "ensure_repository", lambda _: tmp_path)
    monkeypatch.setattr(
        executor,
        "_saved_openai_api_key",
        lambda *_args, **_kwargs: "sk-test-secret-never-log",
    )
    codex_calls = 0
    observed_auth = {}

    def fake_run(args, cwd=None, timeout=900, env_overrides=None):
        nonlocal codex_calls
        if args[:2] == ["git", "switch"]:
            return completed(args)
        if args[:2] == ["git", "status"]:
            return completed(args, stdout="")
        if args[:3] == ["codex", "exec", "--json"]:
            codex_calls += 1
            if not env_overrides:
                return completed(args, code=1, stdout=USAGE_LIMIT_JSONL)
            codex_home = Path(env_overrides["CODEX_HOME"])
            auth_file = codex_home / "auth.json"
            observed_auth.update(
                home_exists=codex_home.is_dir(),
                auth_exists=auth_file.is_file(),
                auth=json.loads(auth_file.read_text(encoding="utf-8")),
                mode=auth_file.stat().st_mode & 0o777,
                env_key=env_overrides.get("OPENAI_API_KEY"),
            )
            return completed(args, stdout='{"type":"turn.completed"}\n')
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(executor, "run", fake_run)
    result = executor.execute_task(project(), task())

    assert codex_calls == 2
    assert observed_auth["home_exists"] is True
    assert observed_auth["auth_exists"] is True
    assert observed_auth["auth"]["auth_mode"] == "api_key"
    assert observed_auth["auth"]["OPENAI_API_KEY"] == "sk-test-secret-never-log"
    assert observed_auth["mode"] == 0o600
    assert observed_auth["env_key"] == "sk-test-secret-never-log"
    assert result["exit_code"] == 0
    assert result["provider"] == "openai-api"
    assert result["auth_mode"] == "api_key"
    assert result["fallback_used"] is True
    assert result["paid_api_fallback"] is True
    assert len(result["attempts"]) == 2
    assert "sk-test-secret-never-log" not in json.dumps(result)


def test_partial_changes_prevent_automatic_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(executor, "get_settings", settings)
    monkeypatch.setattr(executor, "ensure_repository", lambda _: tmp_path)
    monkeypatch.setattr(
        executor,
        "_saved_openai_api_key",
        lambda *_args, **_kwargs: "sk-test-secret-never-log",
    )
    status_calls = 0
    codex_calls = 0

    def fake_run(args, cwd=None, timeout=900, env_overrides=None):
        nonlocal status_calls, codex_calls
        if args[:2] == ["git", "switch"]:
            return completed(args)
        if args[:2] == ["git", "status"]:
            status_calls += 1
            return completed(args, stdout="" if status_calls == 1 else " M app/main.py\n")
        if args[:3] == ["codex", "exec", "--json"]:
            codex_calls += 1
            return completed(args, code=1, stdout=USAGE_LIMIT_JSONL)
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(executor, "run", fake_run)
    result = executor.execute_task(project(), task())

    assert codex_calls == 1
    assert result["blocked"] is True
    assert result["failure_code"] == "partial_changes_detected"
    assert result["fallback_used"] is False
    assert "estado parcial" in result["summary"]
