from app.models import Project


def build_bootstrap_prompt(project: Project, *, generate_agents_md: bool) -> str:
    agents_instruction = (
        "Inspect the repository and create or improve its root AGENTS.md. Derive concrete "
        "commands, architecture boundaries, safety rules, and verification steps from the "
        "actual project; do not use a generic template. "
        if generate_agents_md
        else "Respect the existing AGENTS.md and repository-local instructions. "
    )
    return (
        f"Start the development of {project.name} autonomously.\n\n"
        f"Product context: {project.description or 'Use the repository documentation as context.'}\n\n"
        f"{agents_instruction}"
        "If the repository is empty, create the smallest runnable foundation that matches the "
        "product context, including tests and setup documentation. If it already contains code, "
        "run its documented checks, identify the highest-priority safe improvement, and implement "
        "one focused increment. Keep all work on the isolated task branch. Do not push, merge, "
        "deploy, publish packages, rotate secrets, or perform destructive operations. Finish with "
        "the checks run, evidence, risks, and recommended next task."
    )
