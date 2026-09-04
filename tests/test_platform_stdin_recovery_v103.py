from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: ausente: {needle}")


def main() -> None:
    worker_entry = (ROOT / "app/worker_entry.py").read_text(encoding="utf-8")
    routes = (ROOT / "app/failure_recovery_routes.py").read_text(encoding="utf-8")
    task_runs = (ROOT / "app/task_run_routes.py").read_text(encoding="utf-8")

    require(worker_entry, "_detach_worker_stdin()", "worker fecha stdin no startup")
    require(worker_entry, "os.dup2(devnull_fd, 0)", "stdin aponta para /dev/null")

    require(task_runs, '"executor_runtime": "EXECUTOR_STDIN_BLOCKED"', "código específico")
    require(task_runs, '"reading additional input from stdin"', "assinatura do Codex")
    require(task_runs, 'return "executor_runtime"', "classificação da plataforma")
    require(
        task_runs,
        "O projeto não é a causa desta falha.",
        "mensagem não culpa o projeto",
    )

    require(routes, "def _platform_failure", "reclassificação histórica")
    require(routes, '"code": "EXECUTOR_STDIN_BLOCKED"', "diagnóstico do jogo")
    require(routes, '"action": "requeue_original"', "correção direta")
    require(routes, '"explicit_user_trigger": True', "gatilho explícito")
    require(routes, "def _requeue_platform_failure", "reenfileira origem")
    require(
        routes,
        'action="failure_recovery.platform_runner_requeued"',
        "auditoria do retry da plataforma",
    )
    require(
        routes,
        'if failure.get("category") == "executor_runtime":',
        "escalate não cria recovery de projeto",
    )

    print("PLATFORM_STDIN_RECOVERY_V103=OK")


if __name__ == "__main__":
    main()
