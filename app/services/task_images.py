from __future__ import annotations

import base64
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

from app.config import get_settings


MAX_TASK_IMAGES = 3
MAX_TASK_IMAGE_BYTES = 8 * 1024 * 1024
TASK_IMAGE_MARKER_RE = re.compile(
    r"\[DEVPILOT_IMAGE=(?P<name>[a-f0-9]{32}\.(?:png|jpg|jpeg|webp))\]",
    re.IGNORECASE,
)
IMAGE_ID_RE = re.compile(r"^[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)$", re.IGNORECASE)


_WRAPPER = (
    "import base64,subprocess,sys;"
    "prompt=base64.b64decode(sys.argv[1]).decode('utf-8');"
    "result=subprocess.run(sys.argv[2:],input=prompt,text=True);"
    "raise SystemExit(result.returncode)"
)


def task_images_dir() -> Path:
    directory = get_settings().data_dir / "task-images"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def image_names_from_prompt(prompt: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for match in TASK_IMAGE_MARKER_RE.finditer(str(prompt or "")):
        name = match.group("name").lower()
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names[:MAX_TASK_IMAGES]


def strip_image_markers(prompt: str) -> str:
    clean = TASK_IMAGE_MARKER_RE.sub("", str(prompt or ""))
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def image_paths_from_prompt(prompt: str) -> list[Path]:
    root = task_images_dir().resolve()
    paths: list[Path] = []
    for name in image_names_from_prompt(prompt):
        if not IMAGE_ID_RE.fullmatch(name):
            continue
        path = (root / name).resolve()
        if path.parent != root:
            raise RuntimeError("Caminho de imagem anexada inválido")
        if not path.is_file():
            raise RuntimeError(f"Imagem anexada não está mais disponível: {name}")
        paths.append(path)
    return paths


def build_codex_image_command(
    original_command: Callable,
    project,
    prompt: str,
) -> list[str]:
    paths = image_paths_from_prompt(prompt)
    if not paths:
        return original_command(project, prompt)

    clean_prompt = strip_image_markers(prompt)
    base_command = original_command(project, clean_prompt)
    if not base_command or base_command[-1] != clean_prompt:
        raise RuntimeError("Não foi possível preparar o comando multimodal do Codex")

    command = list(base_command[:-1])
    for path in paths:
        command.extend(["--image", str(path)])

    encoded_prompt = base64.b64encode(clean_prompt.encode("utf-8")).decode("ascii")
    return [sys.executable, "-c", _WRAPPER, encoded_prompt, *command]


def enable_executor_image_support(executor_module: ModuleType) -> None:
    if getattr(executor_module, "_devpilot_image_support_enabled", False):
        return

    original_command = executor_module.codex_command

    def codex_command_with_images(project, prompt: str) -> list[str]:
        return build_codex_image_command(original_command, project, prompt)

    executor_module.codex_command = codex_command_with_images
    executor_module._devpilot_image_support_enabled = True
