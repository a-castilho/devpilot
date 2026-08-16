#!/usr/bin/env python3
"""Start and monitor trusted Docker Compose projects from one local directory.

The manager only runs projects containing a ``.devpilot-autostart`` marker. This
prevents an arbitrary repository clone from executing containers automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


COMPOSE_NAMES = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")
IGNORED_DIRS = {".git", ".venv", "node_modules", "vendor", "dist", "build"}
MARKER = ".devpilot-autostart"
DEFAULT_STATE_FILE = Path.home() / ".local" / "state" / "devpilot" / "docker-projects.json"


@dataclass(frozen=True)
class Project:
    name: str
    directory: Path
    compose_file: Path


def project_name(directory: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", directory.name.lower()).strip("-") or "project"
    suffix = hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:8]
    return f"devpilot-{slug}-{suffix}"


def discover(root: Path) -> list[Project]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Diretório de projetos inexistente: {root}")

    projects: list[Project] = []
    for current, directories, files in os.walk(root):
        directories[:] = sorted(item for item in directories if item not in IGNORED_DIRS)
        current_path = Path(current)
        if MARKER not in files:
            continue
        compose = next((current_path / name for name in COMPOSE_NAMES if name in files), None)
        if compose:
            projects.append(Project(project_name(current_path), current_path, compose))
        directories[:] = []
    return sorted(projects, key=lambda item: str(item.directory))


def docker_command(project: Project, action: str, build: bool = True) -> list[str]:
    base = [
        "docker",
        "compose",
        "--project-name",
        project.name,
        "--project-directory",
        str(project.directory),
        "--file",
        str(project.compose_file),
    ]
    if action == "up":
        return [*base, "up", "--detach", *(["--build"] if build else [])]
    if action == "down":
        return [*base, "down"]
    if action == "status":
        return [*base, "ps", "--format", "json"]
    raise ValueError(f"Ação desconhecida: {action}")


def run_projects(projects: list[Project], action: str, *, build: bool = True) -> int:
    failures = 0
    results: list[dict[str, object]] = []
    for project in projects:
        command = docker_command(project, action, build)
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        ok = completed.returncode == 0
        failures += int(not ok)
        results.append(
            {
                "project": project.name,
                "directory": str(project.directory),
                "action": action,
                "ok": ok,
                "output": (completed.stdout or completed.stderr).strip()[-4000:],
            }
        )
        print(f"[{'OK' if ok else 'FALHA'}] {project.directory}")
        if not ok:
            print(results[-1]["output"], file=sys.stderr)
    print(json.dumps({"projects": results, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def project_fingerprint(project: Project) -> str:
    """Return a cheap source fingerprint without reading file contents or secrets."""
    entries: list[str] = []
    for current, directories, files in os.walk(project.directory):
        directories[:] = sorted(item for item in directories if item not in IGNORED_DIRS)
        current_path = Path(current)
        for filename in sorted(files):
            path = current_path / filename
            if filename == MARKER:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(f"{path.relative_to(project.directory)}:{stat.st_mtime_ns}:{stat.st_size}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def load_state(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def refresh_changed(projects: list[Project], state_file: Path = DEFAULT_STATE_FILE) -> int:
    """Rebuild only explicitly registered projects whose working tree changed."""
    state = load_state(state_file)
    updated = dict(state)
    failures = 0
    changed = 0
    for project in projects:
        fingerprint = project_fingerprint(project)
        key = str(project.directory)
        if state.get(key) == fingerprint:
            continue
        changed += 1
        result = run_projects([project], "up")
        failures += int(result != 0)
        if result == 0:
            updated[key] = fingerprint
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")
    if not changed:
        print("Ambientes já estão atualizados.")
    return 1 if failures else 0


def register(directory: Path) -> int:
    directory = directory.expanduser().resolve()
    compose = next((directory / name for name in COMPOSE_NAMES if (directory / name).is_file()), None)
    if not compose:
        print(f"Nenhum arquivo Docker Compose encontrado em {directory}", file=sys.stderr)
        return 1
    marker = directory / MARKER
    marker.touch(exist_ok=True)
    print(f"Projeto registrado: {directory} ({compose.name})")
    return 0


def install_systemd(root: Path) -> int:
    if not shutil.which("systemctl"):
        print("systemd não está disponível nesta máquina.", file=sys.stderr)
        return 1
    script = Path(__file__).resolve()
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "devpilot-docker-projects.service"
    unit.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=DevPilot Docker projects",
                "After=default.target",
                "",
                "[Service]",
                "Type=oneshot",
                f'ExecStart={sys.executable} {script} refresh --root {root.expanduser().resolve()}',
                "TimeoutStartSec=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    timer = unit_dir / "devpilot-docker-projects.timer"
    timer.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Atualiza ambientes Docker autorizados pelo DevPilot",
                "",
                "[Timer]",
                "OnBootSec=10s",
                "OnUnitActiveSec=30s",
                "AccuracySec=5s",
                "Persistent=true",
                "Unit=devpilot-docker-projects.service",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        ),
        encoding="utf-8",
    )
    commands = (
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", timer.name],
    )
    for command in commands:
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            return completed.returncode
    print(f"Atualização automática instalada: {timer}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    register_parser = subcommands.add_parser("register", help="autoriza um projeto")
    register_parser.add_argument("directory", type=Path)
    for command in ("discover", "sync", "refresh", "status", "down", "install"):
        item = subcommands.add_parser(command)
        item.add_argument("--root", type=Path, default=Path.home() / "Documents")
        if command == "sync":
            item.add_argument("--no-build", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "register":
        return register(args.directory)
    if args.command == "install":
        if not shutil.which("docker"):
            print("Docker não encontrado no PATH.", file=sys.stderr)
            return 1
        return install_systemd(args.root)
    try:
        projects = discover(args.root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if args.command == "discover":
        payload = [
            asdict(item)
            | {"directory": str(item.directory), "compose_file": str(item.compose_file)}
            for item in projects
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not shutil.which("docker"):
        print("Docker não encontrado no PATH.", file=sys.stderr)
        return 1
    if not projects:
        print(f"Nenhum projeto autorizado. Crie {MARKER} com o comando register.")
        return 0
    if args.command == "refresh":
        return refresh_changed(projects)
    return run_projects(projects, "up" if args.command == "sync" else args.command, build=not getattr(args, "no_build", False))


if __name__ == "__main__":
    raise SystemExit(main())
