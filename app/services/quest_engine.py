from __future__ import annotations

from dataclasses import dataclass

from app.models import Task, TaskStatus
from app.quest_models import QuestProfile
from app.security import Role


RANKS = [
    (1, "Observador"),
    (3, "Investigador"),
    (5, "Aprendiz"),
    (8, "Desenvolvedor"),
    (12, "Engenheiro"),
    (16, "Senior Developer"),
    (20, "Tech Lead"),
    (25, "Architect"),
    (30, "DevOps / SRE"),
    (36, "Security Engineer"),
    (42, "System Architect"),
    (50, "System Administrator"),
]

RISK_LABELS = {
    0: "R0 - leitura",
    1: "R1 - local reversível",
    2: "R2 - branch isolada",
    3: "R3 - mudança estrutural",
    4: "R4 - infraestrutura/deploy",
    5: "R5 - produção/segurança/privilégios",
}

MANAGEMENT = {Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN}


@dataclass(frozen=True)
class Reward:
    xp: int
    stars: int
    moons: int
    swords: int


def level_from_xp(xp: int) -> int:
    # Progressão deliberadamente não linear: cada nível exige mais evidência real.
    return max(1, min(50, int((max(0, xp) / 125) ** 0.72) + 1))


def rank_for_level(level: int) -> str:
    rank = RANKS[0][1]
    for required, name in RANKS:
        if level >= required:
            rank = name
    return rank


def classify_task_risk(task: Task) -> int:
    text = f"{task.title} {task.prompt}".lower()
    critical = ("root", "sudo", "produção", "production", "secret", "credential", "rbac", "auth")
    infrastructure = ("deploy", "migration", "database", "banco", "docker", "systemctl", "infra")
    structural = ("arquitetura", "architecture", "refactor", "schema", "structural")
    if any(term in text for term in critical):
        return 5
    if any(term in text for term in infrastructure):
        return 4
    if any(term in text for term in structural):
        return 3
    if task.requires_approval:
        return 2
    return 1


def reward_for(risk: int, difficulty: int) -> Reward:
    risk = max(0, min(5, int(risk)))
    difficulty = max(1, min(5, int(difficulty)))
    xp = 75 + (difficulty * 50) + (risk * 60)
    stars = max(1, difficulty)
    moons = 1 if risk >= 3 else 0
    swords = 1 if risk >= 4 else 0
    return Reward(xp=xp, stars=stars, moons=moons, swords=swords)


def role_can_accept(role: Role, risk: int) -> bool:
    if risk <= 2:
        return role is not Role.VIEWER
    if risk == 3:
        return role in MANAGEMENT or role is Role.ANALYST
    return role in MANAGEMENT


def validate_real_task(task: Task, risk: int) -> tuple[bool, str]:
    if task.status is not TaskStatus.completed:
        return False, "A tarefa real ainda não está concluída"
    if risk >= 3 and task.requires_approval and task.approved_at is None:
        return False, "Missão de risco elevado exige aprovação registrada na tarefa"
    return True, "Tarefa real concluída e evidência mínima validada"


def apply_reward(profile: QuestProfile, reward: Reward) -> QuestProfile:
    profile.xp += reward.xp
    profile.stars += reward.stars
    profile.moons += reward.moons
    profile.swords += reward.swords
    profile.level = level_from_xp(profile.xp)
    profile.rank_name = rank_for_level(profile.level)
    return profile
