from __future__ import annotations

import hashlib
import os
import platform
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx

CODEX_VERSION = "0.153.4"
RELEASE_API = f"https://api.github.com/repos/openai/codex/releases/tags/rust-v{CODEX_VERSION}"
CACHE_ROOT = Path(os.getenv("DEVPILOT_CODEX_RUNTIME_DIR", "/tmp/devpilot-codex"))


def _target() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64-unknown-linux-musl"
    if machine in {"aarch64", "arm64"}:
        return "aarch64-unknown-linux-musl"
    raise RuntimeError(f"Arquitetura não suportada para Codex no worker: {machine}")


def _binary_path() -> Path:
    return CACHE_ROOT / CODEX_VERSION / "codex"


def _download_codex() -> Path:
    target = _target()
    asset_name = f"codex-{target}.tar.gz"
    binary = _binary_path()
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "DevPilot/worker"}
    with httpx.Client(timeout=60.0, follow_redirects=True, headers=headers) as client:
        metadata_response = client.get(RELEASE_API)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        asset = next((item for item in metadata.get("assets", []) if item.get("name") == asset_name), None)
        if not asset:
            raise RuntimeError(f"Asset oficial do Codex não encontrado: {asset_name}")
        url = str(asset.get("browser_download_url") or "")
        digest = str(asset.get("digest") or "")
        if not url or not digest.startswith("sha256:"):
            raise RuntimeError("Metadados oficiais do Codex não contêm URL e SHA-256 verificável")

        response = client.get(url)
        response.raise_for_status()
        payload = response.content

    expected = digest.split(":", 1)[1].lower()
    actual = hashlib.sha256(payload).hexdigest().lower()
    if actual != expected:
        raise RuntimeError("Falha de integridade ao baixar o Codex CLI")

    binary.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="devpilot-codex-") as temp_dir:
        archive = Path(temp_dir) / asset_name
        archive.write_bytes(payload)
        with tarfile.open(archive, "r:gz") as package:
            members = [member for member in package.getmembers() if member.isfile()]
            candidate = next((member for member in members if Path(member.name).name.startswith("codex-")), None)
            if not candidate:
                raise RuntimeError("Binário Codex ausente no pacote oficial")
            extracted = package.extractfile(candidate)
            if extracted is None:
                raise RuntimeError("Não foi possível extrair o Codex CLI")
            temporary_binary = Path(temp_dir) / "codex"
            temporary_binary.write_bytes(extracted.read())
            temporary_binary.chmod(0o755)
            shutil.move(str(temporary_binary), str(binary))
    binary.chmod(0o755)
    return binary


def main() -> None:
    try:
        binary = _download_codex()
    except Exception as error:
        print(f"DevPilot não conseguiu preparar o Codex CLI: {error}", file=sys.stderr)
        raise SystemExit(78) from error
    os.execv(str(binary), [str(binary), *sys.argv[1:]])


if __name__ == "__main__":
    main()
