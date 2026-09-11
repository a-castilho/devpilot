from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_homolog_shell_uses_modern_auth_and_hides_legacy_token_form():
    subprocess.run(
        ["node", "tools/build-vercel-static.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    built = ROOT / ".vercel-static"
    html = (built / "index.html").read_text(encoding="utf-8")
    auth_js = (built / "assets" / "auth-ui.js").read_text(encoding="utf-8")

    assert "DEVPILOT_BOOTSTRAP_TOKEN" not in html
    assert 'id="save-token"' not in html
    assert "Preparando acesso seguro" in html
    assert "autenticação por e-mail e senha" in html
    assert "/assets/auth-ui.js?v=" in html

    # /assets/index.html não pode manter uma segunda rota pública com o login legado.
    assert not (built / "assets" / "index.html").exists()

    # auth-ui deve substituir um shell já aberto pelo core, em vez de abandonar o boot.
    assert "if (modal.open) return;" not in auth_js
    assert "O auth-ui é o dono do pré-login" in auth_js
