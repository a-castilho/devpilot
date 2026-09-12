from app.services import executor
from app.services.github_access_bridge import _git_environment, _repository_owner


def test_repository_owner_accepts_https_and_ssh():
    assert _repository_owner("https://github.com/a-castilho/projeto.git") == "a-castilho"
    assert _repository_owner("git@github.com:a-castilho/projeto.git") == "a-castilho"


def test_git_environment_is_non_interactive_and_uses_header_not_url():
    env = _git_environment("github_pat_example")
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert "github_pat_example" not in env["GIT_CONFIG_VALUE_0"]


def test_executor_repository_checkout_is_installed_through_access_bridge():
    assert getattr(executor.ensure_repository, "_devpilot_repository_access_bridge", False) is True
