from __future__ import annotations

import re

from app.services import executor

_ORIGINAL_DEVELOPMENT_PROMPT = executor.development_prompt
_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_PHASE_2 = re.compile(r"(?mi)^FASE:\s*2/7\s*$")
_PHASE_3_TO_7 = re.compile(r"(?mi)^FASE:\s*[3-7]/7\s*$")

_DELIVERY_CONTRACT = """

MANDATORY DEVpilot DELIVERY CONTRACT
This Build Game round is an end-to-end managed delivery. The final product must use:
- frontend deployed by Vercel;
- backend deployed by Render;
- PostgreSQL database provisioned by Neon.
The repository default branch must therefore become independently deployable. Keep a root Dockerfile for the backend, expose a real GET /health endpoint returning 2xx when ready, use DATABASE_URL for PostgreSQL, and keep the frontend build/configuration compatible with Vercel. Never hard-code provider credentials or database URLs. The DevPilot cloud reconciler injects runtime values and publishes the final URL after health checks pass.
"""


def _prompt(task):
    base = _ORIGINAL_DEVELOPMENT_PROMPT(task)
    raw = str(task.prompt or "")
    if _GAME_MARKER not in raw:
        return base
    if _PHASE_2.search(raw):
        return base + _DELIVERY_CONTRACT + "\nCreate/fix these deployability artifacts in this implementation phase as part of the requested vertical slice."
    if _PHASE_3_TO_7.search(raw):
        return base + _DELIVERY_CONTRACT + "\nPreserve and validate these deployability artifacts; repair them if this phase discovers a defect."
    return base


def install() -> None:
    if getattr(executor.development_prompt, "_devpilot_delivery_contract", False):
        return
    _prompt._devpilot_delivery_contract = True
    executor.development_prompt = _prompt


install()
