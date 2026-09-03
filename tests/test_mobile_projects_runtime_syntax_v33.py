from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "app/static/mobile-project-card-compact.js"


def test_mobile_projects_runtime_javascript_syntax():
    node = shutil.which("node")
    if not node:
        return
    subprocess.run([node, "--check", str(MOBILE)], check=True, capture_output=True, text=True)
