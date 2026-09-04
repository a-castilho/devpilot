from pathlib import Path


worker_entry = Path("app/worker_entry.py").read_text(encoding="utf-8")
compose = Path("docker-compose.yml").read_text(encoding="utf-8")

assert "DEVPILOT_WORKER_RECOVER_RUNNING_ON_START" in worker_entry
assert "_recover_orphaned_running_tasks" in worker_entry
assert 'TASK_RUNTIME.c.state == "running"' in worker_entry
assert 'TASK_RUNTIME.c.claim_owner.like("worker:%")' in worker_entry
assert "task.status = TaskStatus.queued" in worker_entry
assert 'state="queued"' in worker_entry
assert 'claim_owner=""' in worker_entry
assert "lease_expires_at=None" in worker_entry
assert "worker_restart_recovered" in worker_entry
assert 'DEVPILOT_WORKER_RECOVER_RUNNING_ON_START: "true"' in compose

print("WORKER_RESTART_RECOVERY_V101=OK")
