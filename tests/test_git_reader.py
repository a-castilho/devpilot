from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import git_reader


def project():
    return SimpleNamespace(
        default_branch="main",
        repository_url="https://github.com/a-castilho/devpilot.git",
    )


def test_repository_ref_defaults_to_origin_branch():
    assert git_reader.repository_ref(project()) == "origin/main"


def test_repository_ref_rejects_revision_expression():
    with pytest.raises(ValueError):
        git_reader.repository_ref(project(), "main..production")


def test_repository_file_path_rejects_traversal():
    with pytest.raises(ValueError):
        git_reader.repository_file_path("../.env")


def test_git_grep_parses_tree_matches(monkeypatch):
    monkeypatch.setattr(git_reader, "ensure_repository", lambda _: Path("/tmp/repository"))

    def fake_run(args, cwd=None, timeout=60):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "origin/main:app/api.py:42:Marketplace Fiscal\n"
                "origin/main:README.md:7:Marketplace Fiscal\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(git_reader, "run", fake_run)

    matches = git_reader.grep(project(), "Marketplace Fiscal", limit=10)

    assert matches == [
        {"path": "app/api.py", "line": 42, "text": "Marketplace Fiscal"},
        {"path": "README.md", "line": 7, "text": "Marketplace Fiscal"},
    ]
