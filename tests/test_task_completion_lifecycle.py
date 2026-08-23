from sqlalchemy import create_engine, text

from app.models import TaskStatus
from app.services.schema import ensure_runtime_schema
from app.worker import _final_task_status


def test_successful_run_finishes_task_as_completed():
    assert _final_task_status("success", needs_authorization=False) == TaskStatus.completed
    assert _final_task_status("success", needs_authorization=True) == TaskStatus.completed


def test_failed_run_preserves_blocked_and_failed_outcomes():
    assert _final_task_status("failed", needs_authorization=True) == TaskStatus.blocked
    assert _final_task_status("failed", needs_authorization=False) == TaskStatus.failed


def test_runtime_schema_backfills_legacy_review_tasks():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE tasks (id VARCHAR(36) PRIMARY KEY, status VARCHAR(30) NOT NULL)")
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id, status) VALUES "
                "('legacy-review', 'review'), "
                "('already-complete', 'completed'), "
                "('still-running', 'running')"
            )
        )

    ensure_runtime_schema(engine)

    with engine.connect() as connection:
        statuses = dict(connection.execute(text("SELECT id, status FROM tasks")).all())

    assert statuses["legacy-review"] == "completed"
    assert statuses["already-complete"] == "completed"
    assert statuses["still-running"] == "running"
