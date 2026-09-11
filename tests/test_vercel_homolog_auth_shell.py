from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_homolog_shell_never_exposes_legacy_bootstrap_token_form(tmp_path):
    subprocess.run(
        ["node", "tools/build-vercel-static.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    html = (ROOT / ".vercel-static" / "index.html").read_text(encoding="utf-8")

    assert "DEVPILOT_BOOTSTRAP_TOKEN" not in html
    assert 'id="save-token"' not in html
    assert "Preparando acesso seguro" in html
    assert "/assets/auth-ui.js?v=" in html
    assert "autenticação por e-mail e senha" in html
