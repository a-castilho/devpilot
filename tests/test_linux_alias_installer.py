import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/instalar-aliases-linux.sh"
START = "# >>> DEVPILOT ALIASES >>>"
END = "# <<< DEVPILOT ALIASES <<<"


def _run_installer(home: Path) -> None:
    env = os.environ.copy()
    env["HOME"] = str(home)
    subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_installer_is_idempotent_and_neutralizes_legacy_alias_conflicts(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text(
        "\n".join(
            [
                "alias atualizar='echo legacy-update'",
                "alias atualizar-local='echo legacy-local'",
                "alias reconstruir='echo legacy-rebuild'",
                "alias reconstruir-sistema='echo legacy-system'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _run_installer(home)
    _run_installer(home)

    source = bashrc.read_text(encoding="utf-8")
    assert source.count(START) == 1
    assert source.count(END) == 1
    assert (
        "unalias subir-projeto subir atualizar-local atualizar "
        "reconstruir-sistema reconstruir 2>/dev/null || true"
    ) in source

    subprocess.run(["bash", "-n", str(bashrc)], check=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--rcfile",
            str(bashrc),
            "-ic",
            "printf 'DP_ATUALIZAR_LOCAL=%s\\n' \"$(type -t atualizar-local)\"; "
            "printf 'DP_ATUALIZAR=%s\\n' \"$(type -t atualizar)\"; "
            "printf 'DP_RECONSTRUIR_SISTEMA=%s\\n' \"$(type -t reconstruir-sistema)\"; "
            "printf 'DP_RECONSTRUIR=%s\\n' \"$(type -t reconstruir)\"",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    shell_types = {
        line
        for line in result.stdout.splitlines()
        if line.startswith("DP_")
    }
    assert shell_types == {
        "DP_ATUALIZAR_LOCAL=function",
        "DP_ATUALIZAR=function",
        "DP_RECONSTRUIR_SISTEMA=function",
        "DP_RECONSTRUIR=function",
    }


def test_installer_validates_candidate_before_replacing_bashrc():
    source = INSTALLER.read_text(encoding="utf-8")

    assert 'if ! bash -n "$TMP"; then' in source
    assert 'cat "$TMP" > "$RC_FILE"' in source
    assert source.index('bash -n "$TMP"') < source.index('cat "$TMP" > "$RC_FILE"')
