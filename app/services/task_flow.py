from __future__ import annotations

import re

from app.models import Task


FLOW_MARKER = "[DEVPILOT_FLOW=analysis-execute-verify-correct]"
ACTION_MARKER = "[analysis-action]"
VERIFICATION_MARKER = "[post-execution-verification]"
IMPLEMENTATION_STAGE_MARKER = "[DEVPILOT_STAGE=execute]"
VERIFICATION_STAGE_MARKER = "[DEVPILOT_STAGE=verify]"
CORRECTION_STAGE_MARKER = "[DEVPILOT_STAGE=correct]"
ANALYSIS_MODES = {"analysis-read-only", "review"}
EXECUTION_MODES = {"develop", "fix"}

_LEGACY_ACTION_SIGNALS = (
    "correção baseada na análise",
    "correcao baseada na analise",
    "ação recomendada",
    "acao recomendada",
    "execute as correções",
    "execute as correcoes",
    "não faça uma nova análise",
    "nao faca uma nova analise",
)
_LEGACY_ANALYSIS_SIGNALS = (
    "análise técnica de ",
    "analise tecnica de ",
    "auditoria somente leitura",
    "somente leitura do projeto",
    "não modifique arquivos",
    "nao modifique arquivos",
)
_MODE_RE = re.compile(r"\[DEVPILOT_MODE=([^\]]+)\]", re.IGNORECASE)
_BRANCH_RE = re.compile(r"\[execution-branch:([^\]\r\n]+)\]", re.IGNORECASE)
_EXECUTION_TASK_RE = re.compile(r"\[execution-task:([^\]\r\n]+)\]", re.IGNORECASE)


def task_mode(task: Task) -> str:
    match = _MODE_RE.search(str(task.prompt or ""))
    return match.group(1).strip().lower() if match else ""


def flow_stage(task: Task) -> str:
    prompt = str(task.prompt or "").casefold()
    if CORRECTION_STAGE_MARKER.casefold() in prompt:
        return "correct"
    if VERIFICATION_STAGE_MARKER.casefold() in prompt or VERIFICATION_MARKER.casefold() in prompt:
        return "verify"
    if IMPLEMENTATION_STAGE_MARKER.casefold() in prompt or ACTION_MARKER.casefold() in prompt:
        return "execute"
    return ""


def execution_branch(task: Task) -> str:
    match = _BRANCH_RE.search(str(task.prompt or ""))
    return match.group(1).strip() if match else ""


def execution_task_id(task: Task) -> str:
    match = _EXECUTION_TASK_RE.search(str(task.prompt or ""))
    return match.group(1).strip() if match else ""


def is_analysis_action_task(task: Task) -> bool:
    prompt = str(task.prompt or "")
    text = f"{task.title or ''}\n{prompt}".casefold()
    source = str(task.source or "").casefold()

    if source in {"analysis", "analysis-action"}:
        return True
    if ACTION_MARKER.casefold() in text or "[analysis-run:" in text:
        return True
    if CORRECTION_STAGE_MARKER.casefold() in text or IMPLEMENTATION_STAGE_MARKER.casefold() in text:
        return True
    return any(signal.casefold() in text for signal in _LEGACY_ACTION_SIGNALS)


def is_verification_analysis(task: Task) -> bool:
    prompt = str(task.prompt or "").casefold()
    source = str(task.source or "").casefold()
    return (
        source == "execution-verification"
        or VERIFICATION_MARKER.casefold() in prompt
        or VERIFICATION_STAGE_MARKER.casefold() in prompt
    )


def is_correction_action(task: Task) -> bool:
    return CORRECTION_STAGE_MARKER.casefold() in str(task.prompt or "").casefold()


def is_analysis_task(task: Task) -> bool:
    if is_analysis_action_task(task):
        return False
    if is_verification_analysis(task):
        return True

    mode = task_mode(task)
    if mode:
        return mode in ANALYSIS_MODES

    legacy = f"{task.title or ''}\n{task.prompt or ''}".casefold()
    return any(signal.casefold() in legacy for signal in _LEGACY_ANALYSIS_SIGNALS)


def is_read_only_task(task: Task) -> bool:
    """Classify runtime mode with execution/action markers taking precedence.

    Analysis reports are embedded in generated implementation tasks and can contain
    phrases such as "não modifique arquivos". Those phrases describe the completed
    analysis and must never turn the following action back into read-only analysis.
    """
    if is_analysis_action_task(task):
        return False
    if is_verification_analysis(task):
        return True

    mode = task_mode(task)
    if mode in EXECUTION_MODES:
        return False
    if mode in ANALYSIS_MODES:
        return True

    legacy = f"{task.title or ''}\n{task.prompt or ''}".casefold()
    return any(signal.casefold() in legacy for signal in _LEGACY_ANALYSIS_SIGNALS)
