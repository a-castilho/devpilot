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
CACHE_ROOT = Path(os.getenv("DEVPILOT_CODEX_RUNTIME_DIR", "/tmp/devpilot-codex"))
ASSETS = {
    "x86_64": {
        "name": "codex-x86_64-unknown-linux-musl.tar.gz",
        "url": "https://github.com/openai/codex/releases/download/rust-v0.153.4/codex-x86_64-unknown-linux-musl.tar.gz",
        "sha256": "f479424eca092484dc40d87ae28c44f4cc40234a60045d6131e493800d814a30",
    },
    "aarch64": {
        "name": "codex-aarch64-unknown-linux-musl.tar.gz",
        "url": "https://github.com/openai/codex/releases/download/rust-v0.153.4/codex-aarch64-unknown-linux-musl.tar.gz",
        "sha256": "5cda6182bd94c3a30f2eb63a495489ebf7f691fddb14d70f48c6c1a5071b6cde",
    },
}


def _architecture() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    raise RuntimeError(f"Arquitetura não suportada para Codex no worker: {machine}")


def _binary_path() -> Path:
    return CACHE_ROOT / CODEX_VERSION / "codex"


def _download_codex() -> Path:
    asset = ASSETS[_architecture()]
    asset_name = asset["name"]
    binary = _binary_path()
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary

    headers = {"User-Agent": "DevPilot/worker"}
    with httpx.Client(timeout=120.0, follow_redirects=True, headers=headers) as client:
        response = client.get(asset["url"])
        response.raise_for_status()
        payload = response.content

    actual = hashlib.sha256(payload).hexdigest().lower()
    if actual != asset["sha256"]:
        raise RuntimeError("Falha de integridade ao baixar o Codex CLI")

    binary.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="devpilot-codex-") as temp_dir:
        archive = Path(temp_dir) / asset_name
        archive.write_bytes(payload)
        with tarfile.open(archive, "r:gz") as package:
            members = [member for member in package.getmembers() if member.isfile()]
            candidate = next(
                (
                    member
                    for member in members
                    if Path(member.name).name.startswith("codex-")
                ),
                None,
            )
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
