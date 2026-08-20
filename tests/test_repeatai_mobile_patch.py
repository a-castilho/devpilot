from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts" / "corrigir-repeatai-mobile.py"


def run_patcher(project: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["REPETAI_HOME"] = str(project)
    return subprocess.run(
        [sys.executable, str(PATCHER)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_repeatai_mobile_patch_is_safe_and_idempotent(tmp_path: Path):
    project = tmp_path / "repeatai"
    static = project / "static"
    static.mkdir(parents=True)

    index = static / "index.html"
    index.write_text(
        """<!doctype html>
<html>
<head><title>RepetAI</title></head>
<body>
<h2>Eventos recentes</h2>
<h2>Padrões detectados</h2>
<button id="analyze" disabled>Analisar</button>
<script>
document.addEventListener("mousemove", () => {});
document.addEventListener("click", () => {});
</script>
</body>
</html>
""",
        encoding="utf-8",
    )

    first = run_patcher(project)
    assert first.returncode == 0, first.stderr
    content = index.read_text(encoding="utf-8")

    assert "REPETAI_PERFORMANCE_GUARD_V3" in content
    assert "EVENT_INTERVAL_MS = 100" in content
    assert "lastMouseAt" in content
    assert "stopImmediatePropagation" in content
    assert "button.click()" not in content
    assert "autoAnalyzeRetries" not in content
    assert "table-layout: fixed" in content

    backups = list(static.glob("index.html.backup-*"))
    assert len(backups) == 1

    second = run_patcher(project)
    assert second.returncode == 0, second.stderr
    assert "já aplicado" in second.stdout
    assert index.read_text(encoding="utf-8").count(
        "REPETAI_PERFORMANCE_GUARD_V3"
    ) == 3
    assert len(list(static.glob("index.html.backup-*"))) == 1


def test_repeatai_mobile_patch_skips_missing_project(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    result = run_patcher(missing)

    assert result.returncode == 0
    assert "SKIP" in result.stdout
