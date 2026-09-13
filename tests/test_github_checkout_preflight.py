from types import SimpleNamespace

import pytest

from app.services import github_access_bridge
from app.services.github_checkout import (
    GitHubRepositoryAccessError,
    _resolved_git_environment,
    ensure_repository,
)


class Result:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def project():
    return SimpleNamespace(
        id="project-1",
        workspace_id="workspace-1",
        organization_id=None,
        slug="private-project",
        repository_url="https://github.com/example/private-project.git",
    )


def test_public_repository_uses_anonymous_preflight(monkeypatch):
    commands = []

    def run_command(args, **kwargs):
        commands.append((args, kwargs))
        return Result(0)

    monkeypatch.setattr(
        github_access_bridge,
        "resolve_github_access",
        lambda *_args, **_kwargs: pytest.fail("credential resolver must not run for a public repository"),
    )

    environment = _resolved_git_environment(project(), run_command)

    assert environment == {"GIT_TERMINAL_PROMPT": "0"}
    assert commands == [
        (["git", "ls-remote", "https://github.com/example/private-project.git", "HEAD"], {
            "timeout": 45,
            "env_overrides": {"GIT_TERMINAL_PROMPT": "0"},
        })
    ]


def test_private_repository_stops_before_clone_when_no_workspace_credential_works(monkeypatch):
    commands = []

    def run_command(args, **kwargs):
        commands.append((args, kwargs))
        return Result(128, "authentication required")

    monkeypatch.setattr(
        github_access_bridge,
        "resolve_github_access",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=False,
            environment={"GIT_TERMINAL_PROMPT": "0"},
            message="Nenhuma credencial GitHub administrativa cadastrada no workspace possui acesso ao repositório.",
        ),
    )

    with pytest.raises(GitHubRepositoryAccessError, match="repository access denied"):
        _resolved_git_environment(project(), run_command)

    assert len(commands) == 1
    assert commands[0][0][:2] == ["git", "ls-remote"]
    assert all("clone" not in args for args, _kwargs in commands)
    assert all("fetch" not in args for args, _kwargs in commands)


def test_checkout_uses_proven_workspace_credential_for_clone_and_fetch(monkeypatch, tmp_path):
    commands = []
    authenticated_environment = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": "Authorization: Basic redacted-test-value",
    }

    def run_command(args, **kwargs):
        commands.append((args, kwargs))
        if args[:2] == ["git", "ls-remote"]:
            return Result(128, "authentication required")
        return Result(0)

    monkeypatch.setattr(
        github_access_bridge,
        "resolve_github_access",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=True,
            environment=authenticated_environment,
            message="Credencial validada.",
        ),
    )
    monkeypatch.setattr("app.services.github_checkout._repository_path", lambda _project: tmp_path / "checkout")

    path = ensure_repository(project(), run_command)

    assert path == tmp_path / "checkout"
    assert [args[1] for args, _kwargs in commands] == ["ls-remote", "clone", "fetch"]
    assert commands[1][1]["env_overrides"] == authenticated_environment
    assert commands[2][1]["env_overrides"] == authenticated_environment
