from __future__ import annotations

from pathlib import Path
import tomllib

from app.main import app, health
from app.version import __version__


RELEASE_VERSION = "1.1.0"


def test_release_version_is_1_1_0():
    assert __version__ == RELEASE_VERSION
    assert app.version == RELEASE_VERSION
    assert health()["version"] == RELEASE_VERSION


def test_package_uses_app_version_as_single_source_of_truth():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "version" not in project["project"]
    assert "version" in project["project"]["dynamic"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "app.version.__version__"
    }
