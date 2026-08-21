from __future__ import annotations

from pathlib import Path
import tomllib

from app.main import app, health
from app.version import __version__


def test_release_version_is_consistent():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == __version__
    assert app.version == __version__
    assert health()["version"] == __version__
