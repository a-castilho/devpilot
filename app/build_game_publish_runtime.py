from __future__ import annotations

from app.build_game_publish import publish_build_game_phase
from app.services import alternating_flow

_ORIGINAL_EXECUTE_TASK = alternating_flow.execute_task


def _execute_and_publish(project, task):
    result = _ORIGINAL_EXECUTE_TASK(project, task)
    if isinstance(result, dict):
        return publish_build_game_phase(project, task, result)
    return result


def install() -> None:
    if getattr(alternating_flow.execute_task, "_devpilot_build_game_publish", False):
        return
    _execute_and_publish._devpilot_build_game_publish = True
    alternating_flow.execute_task = _execute_and_publish


install()
