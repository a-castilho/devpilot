from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Task, TaskStatus

log = logging.getLogger(__name__)

GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
PIPELINE_MARKER = "[DEVPILOT_BUILD_GAME_PIPELINE_V2]"
VERIFIER_MARKER = "[DEVPILOT_DELIVERY_VERIFIER_V1]"
SERVER_MARKER = "[DEVPILOT_GAME_SERVER_ORCHESTRATED_V1]"
MAX_PHASES = 7
MAX_AUTOMATIC_RETRIES = 3
POLL_SECONDS = 3.0
STALE_QUEUE_MINUTES = 5

PHASES = {
    1: ("Planejamento", "Transforme o pedido em plano e critérios de aceite verificáveis. Leia AGENTS.md e a documentação, preserve literalmente o objetivo, registre .devpilot/build-game.md e execute o baseline. Não implemente nesta fase."),
    2: ("Implementação", "Implemente a funcionalidade descrita no objetivo e no contrato .devpilot/build-game.md como uma fatia vertical completa e utilizável. Produza mudança material e registre git status --short e git diff --stat."),
    3: ("Execução", "Suba o sistema pela forma oficial do repositório, aplique migrações e build quando aplicável, faça health check e smoke reais, corrija erros de runtime e registre evidências."),
    4: ("Testes", "Crie ou atualize testes que provem os critérios de aceite. Cubra caminho feliz, falhas e regressões aplicáveis. Execute testes, lint, typecheck e build existentes e corrija até ficar verde."),
    5: ("Documentação", "Atualize a documentação e .devpilot/build-game.md com uso, configuração, decisões, comandos, evidências e limitações reais."),
    6: ("Git", "Revise status e diff, confirme ausência de segredos, mantenha a entrega reversível e registre branch, commit e diff stat. Push/PR/merge/deploy somente conforme as regras do projeto."),
    7: ("Entrega e revisão", "Compare o objetivo literal com cada critério de aceite, execute smoke final como o usuário utilizará, revise segurança, responsividade, documentação e Git e registre a ENTREGA DA RODADA."),
}

ACTIVE = {
    TaskStatus.queued,
    TaskStatus.planning,
    TaskStatus.awaiting_approval,
    TaskStatus.running,
    TaskStatus.review,
    TaskStatus.blocked,
}
FAILED = {TaskStatus.failed}

_VALUE_RE = re.compile(r"^(?P<label>[A-Z_]+):\s*(?P<value>.+)$", re.MULTILINE)


def _fields(prompt: str) -> dict[str, str]:
    return {match.group("label"): match.group("value").strip() for match in _VALUE_RE.finditer(prompt or "")}


def _is_game(task: Task) -> bool:
    return GAME_MARKER in (task.prompt or "") or (task.title or "").startswith("[Jogo]")


def _is_verifier(task: Task) -> bool:
    return VERIFIER_MARKER in (task.prompt or "") or (task.title or "").startswith("[Jogo] Gate")


def _identity(task: Task) -> tuple[str, str, int] | None:
    values = _fields(task.prompt or "")
    mission = values.get("PARTIDA", "")
    raw_phase = values.get("FASE", "").split("/", 1)[0]
    try:
        phase = int(raw_phase)
    except ValueError:
        return None
    if not mission or not (1 <= phase <= MAX_PHASES):
        return None
    return task.project_id, mission, phase


def _goal(task: Task) -> str:
    return _fields(task.prompt or "").get("OBJETIVO", "").strip()


def _phase_prompt(mission: str, phase: int, goal: str, retry_context: str = "") -> str:
    name, instruction = PHASES[phase]
    retry = f"\n\nCONTEXTO DA TENTATIVA ANTERIOR:\n{retry_context.strip()}\nUse esta resposta para corrigir a nova tentativa." if retry_context.strip() else ""
    return (
        f"{GAME_MARKER}\n{PIPELINE_MARKER}\n{SERVER_MARKER}\n[DEVPILOT_MODE=develop]\n"
        f"PARTIDA: {mission}\nFASE: {phase}/{MAX_PHASES}\nOBJETIVO: {goal}\n\n"
        f"MISSÃO DA FASE: {name}\n{instruction}\n\n"
        "CONTRATO DE PROGRESSÃO REAL:\n"
        "- Preserve o objetivo literal da rodada.\n"
        "- Registre estado antes/depois e verificações realmente executadas.\n"
        "- Se evidência obrigatória estiver ausente, NÃO marque como concluída.\n"
        "- Não avance para outra fase nesta tarefa; o orquestrador do servidor fará isso após o gate independente."
        f"{retry}"
    )


def _gate_prompt(mission: str, phase: int, goal: str, source_task_id: str) -> str:
    return (
        f"{GAME_MARKER}\n{VERIFIER_MARKER}\n{PIPELINE_MARKER}\n{SERVER_MARKER}\n[DEVPILOT_MODE=develop]\n"
        f"PARTIDA: {mission}\nFASE: {phase}/{MAX_PHASES}\nOBJETIVO: {goal}\nORIGEM_EXECUCAO: {source_task_id}\n\n"
        "MISSÃO: VERIFICAR ENTREGA REAL\n"
        "Você é o gate independente. Não aceite status completed como prova suficiente. Inspecione o projeto e prove que a fase existe de verdade. "
        "Leia AGENTS.md, documentação e .devpilot/build-game.md; compare critérios de aceite; execute testes/lint/build/smoke aplicáveis; registre evidências. "
        "Se qualquer critério obrigatório não puder ser provado, NÃO conclua."
    )


def _new_task(source: Task, *, title: str, prompt: str, priority: int) -> Task:
    return Task(
        workspace_id=source.workspace_id,
        owner_user_id=source.owner_user_id,
        project_id=source.project_id,
        title=title,
        prompt=prompt,
        source="game",
        status=TaskStatus.queued,
        priority=min(100, priority),
        requires_approval=False,
    )


def _latest_run_context(task: Task) -> str:
    if not task.runs:
        return ""
    run = sorted(task.runs, key=lambda item: item.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]
    parts = [run.summary or "", run.logs or ""]
    return "\n".join(part.strip() for part in parts if part and part.strip())[-6000:]


class GameRoundOrchestrator:
    """Server-side progression for game rounds.

    The browser becomes an observer. A round keeps advancing while the API process is
    alive, even when the user closes the game page.
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="devpilot-game-orchestrator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            try:
                self.tick()
            except Exception:  # pragma: no cover - defensive background loop
                log.exception("game orchestrator tick failed")

    def tick(self) -> int:
        created = 0
        with SessionLocal() as db:
            tasks = db.scalars(
                select(Task)
                .where(Task.prompt.contains(GAME_MARKER))
                .order_by(Task.created_at.desc())
                .limit(1200)
            ).all()

            groups: dict[tuple[str, str], list[Task]] = defaultdict(list)
            for task in tasks:
                identity = _identity(task)
                if not identity:
                    continue
                project_id, mission, _ = identity
                groups[(project_id, mission)].append(task)

            for (_project_id, mission), mission_tasks in groups.items():
                created += self._advance_mission(db, mission, mission_tasks)

            if created:
                db.commit()
        return created

    def _advance_mission(self, db, mission: str, tasks: list[Task]) -> int:
        tasks.sort(key=lambda task: task.created_at, reverse=True)
        source = tasks[0]
        goal = next((_goal(task) for task in tasks if _goal(task)), "")
        if not goal:
            return 0

        by_phase: dict[int, list[Task]] = defaultdict(list)
        for task in tasks:
            identity = _identity(task)
            if identity:
                by_phase[identity[2]].append(task)

        for phase in range(1, MAX_PHASES + 1):
            phase_tasks = by_phase.get(phase, [])
            bases = [task for task in phase_tasks if not _is_verifier(task)]
            gates = [task for task in phase_tasks if _is_verifier(task)]
            bases.sort(key=lambda task: task.created_at, reverse=True)
            gates.sort(key=lambda task: task.created_at, reverse=True)

            latest_base = bases[0] if bases else None
            latest_gate = gates[0] if gates else None

            if latest_gate and latest_gate.status == TaskStatus.completed:
                continue

            if latest_gate:
                if latest_gate.status in ACTIVE:
                    return 0
                if latest_gate.status in FAILED and len(gates) < MAX_AUTOMATIC_RETRIES:
                    db.add(_new_task(
                        source,
                        title=f"[Jogo] Gate {phase} · Verificar entrega real",
                        prompt=_gate_prompt(mission, phase, goal, latest_base.id if latest_base else latest_gate.id),
                        priority=84 + phase * 2,
                    ))
                    return 1
                return 0

            if latest_base:
                if latest_base.status == TaskStatus.completed:
                    db.add(_new_task(
                        source,
                        title=f"[Jogo] Gate {phase} · Verificar entrega real",
                        prompt=_gate_prompt(mission, phase, goal, latest_base.id),
                        priority=84 + phase * 2,
                    ))
                    return 1
                if latest_base.status in ACTIVE:
                    self._log_stale_queue(latest_base)
                    return 0
                if latest_base.status in FAILED and len(bases) < MAX_AUTOMATIC_RETRIES:
                    db.add(_new_task(
                        source,
                        title=f"[Jogo] Etapa {phase} · {PHASES[phase][0]}",
                        prompt=_phase_prompt(mission, phase, goal, _latest_run_context(latest_base)),
                        priority=68 + phase * 5,
                    ))
                    return 1
                return 0

            # Phase 1 is created transactionally by the start action. Later phases are
            # exclusively owned by this server-side orchestrator.
            if phase == 1:
                return 0
            previous_gates = [task for task in by_phase.get(phase - 1, []) if _is_verifier(task)]
            if any(task.status == TaskStatus.completed for task in previous_gates):
                db.add(_new_task(
                    source,
                    title=f"[Jogo] Etapa {phase} · {PHASES[phase][0]}",
                    prompt=_phase_prompt(mission, phase, goal),
                    priority=68 + phase * 5,
                ))
                return 1
            return 0

        return 0

    @staticmethod
    def _log_stale_queue(task: Task) -> None:
        if task.status != TaskStatus.queued or not task.created_at:
            return
        created_at = task.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at >= timedelta(minutes=STALE_QUEUE_MINUTES):
            log.warning("game task stale in queue task_id=%s project_id=%s age>=5m", task.id, task.project_id)
