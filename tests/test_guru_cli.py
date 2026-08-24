from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from app.cli import guru_analyze


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def test_guru_analyze_current_project(tmp_path: Path, monkeypatch, capsys) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "devpilot@example.invalid")
    _git(tmp_path, "config", "user.name", "DevPilot Test")

    (tmp_path / "README.md").write_text("# Projeto\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Regras\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("APP_ENV=test\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "app" / "security.py").write_text("# security\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    for index in range(5):
        (tmp_path / "tests" / f"test_{index}.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    _git(tmp_path, "remote", "add", "origin", "https://example.invalid/sample.git")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEVPILOT_GURU_AI", "0")
    args = argparse.Namespace(
        project="current",
        include="git,code,tests,deploy,security,docs,product",
        save_history=True,
        game_sync=True,
    )

    assert guru_analyze(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["guru"] == "O Guru"
    assert report["project"] == tmp_path.name
    assert 0 <= report["score"] <= 100
    assert report["signals"]["git"]["has_remote"] is True
    assert report["signals"]["tests"]["test_files"] >= 5
    assert report["game"]["guru_score"] == report["score"]
    assert (tmp_path / ".devpilot" / "guru-history.jsonl").exists()
    assert (tmp_path / ".devpilot" / "guru-game.json").exists()
