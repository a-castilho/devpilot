from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _postgres_enum_name(inspector, table: str, column_name: str) -> str | None:
    for column in inspector.get_columns(table):
        if column["name"] != column_name:
            continue
        column_type = column.get("type")
        values = getattr(column_type, "enums", None)
        name = getattr(column_type, "name", None)
        if values and name:
            return str(name)
    return None


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements: list[str] = []

    if "projects" in tables:
        project_columns = _column_names(inspector, "projects")
        if "organization_id" not in project_columns:
            statements.extend(
                [
                    "ALTER TABLE projects ADD COLUMN organization_id VARCHAR(36)",
                    "CREATE INDEX IF NOT EXISTS ix_projects_organization_id ON projects (organization_id)",
                ]
            )
        if "owner_user_id" not in project_columns:
            statements.extend(
                [
                    "ALTER TABLE projects ADD COLUMN owner_user_id VARCHAR(36)",
                    "CREATE INDEX IF NOT EXISTS ix_projects_owner_user_id ON projects (owner_user_id)",
                ]
            )

    # Older workers left successful executions in review even though the product
    # has no post-run review transition. Normalize only that dead-end state.
    if "tasks" in tables:
        task_columns = _column_names(inspector, "tasks")
        if "owner_user_id" not in task_columns:
            statements.extend(
                [
                    "ALTER TABLE tasks ADD COLUMN owner_user_id VARCHAR(36)",
                    "CREATE INDEX IF NOT EXISTS ix_tasks_owner_user_id ON tasks (owner_user_id)",
                ]
            )
        statements.append("UPDATE tasks SET status = 'completed' WHERE status = 'review'")

    # Base.metadata.create_all() creates new Investia tables, but it cannot evolve a
    # persistent PostgreSQL volume that already has an older version of the table.
    # Keep the runtime migration additive so old DevPilot installations can publish
    # projects without failing with a generic HTTP 500.
    if "investia_project_configs" in tables:
        investia_columns = _column_names(inspector, "investia_project_configs")
        if "public_enabled" not in investia_columns:
            statements.append(
                "ALTER TABLE investia_project_configs ADD COLUMN public_enabled BOOLEAN DEFAULT FALSE"
            )
        if "notes" not in investia_columns:
            statements.append(
                "ALTER TABLE investia_project_configs ADD COLUMN notes TEXT DEFAULT ''"
            )
        if "updated_at" not in investia_columns:
            statements.append(
                "ALTER TABLE investia_project_configs ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE"
                if engine.dialect.name == "postgresql"
                else "ALTER TABLE investia_project_configs ADD COLUMN updated_at DATETIME"
            )
        statements.extend(
            [
                "UPDATE investia_project_configs SET public_enabled = FALSE WHERE public_enabled IS NULL",
                "UPDATE investia_project_configs SET notes = '' WHERE notes IS NULL",
            ]
        )

        # SQLAlchemy Enum types are persistent PostgreSQL objects. If an older
        # database created the enum before newer publication states existed, add
        # the values in-place instead of requiring the volume to be recreated.
        if engine.dialect.name == "postgresql":
            enum_name = _postgres_enum_name(inspector, "investia_project_configs", "status")
            if enum_name:
                for value in (
                    "draft",
                    "fundraising",
                    "funded",
                    "operating",
                    "distributing",
                    "completed",
                    "paused",
                    "cancelled",
                ):
                    statements.append(
                        f'ALTER TYPE "{enum_name}" ADD VALUE IF NOT EXISTS \'{value}\''
                    )

    if "users" in tables:
        statements.extend(
            [
                "UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'admin'",
                "UPDATE users SET role = 'VIEWER' WHERE role = 'user'",
            ]
        )

        # Legacy DevPilot data predates per-account ownership. Assign those rows to
        # the persisted SUPER_ADMIN of the same workspace instead of exposing them
        # to every newly-created user. Tasks inherit the owner of their project.
        if "projects" in tables:
            statements.append(
                """
                UPDATE projects
                SET owner_user_id = (
                    SELECT users.id
                    FROM users
                    WHERE users.workspace_id = projects.workspace_id
                      AND users.role = 'SUPER_ADMIN'
                    ORDER BY users.created_at ASC, users.id ASC
                    LIMIT 1
                )
                WHERE owner_user_id IS NULL
                """
            )
        if "tasks" in tables and "projects" in tables:
            statements.append(
                """
                UPDATE tasks
                SET owner_user_id = (
                    SELECT projects.owner_user_id
                    FROM projects
                    WHERE projects.id = tasks.project_id
                    LIMIT 1
                )
                WHERE owner_user_id IS NULL
                """
            )
        if "tasks" in tables:
            statements.append(
                """
                UPDATE tasks
                SET owner_user_id = (
                    SELECT users.id
                    FROM users
                    WHERE users.workspace_id = tasks.workspace_id
                      AND users.role = 'SUPER_ADMIN'
                    ORDER BY users.created_at ASC, users.id ASC
                    LIMIT 1
                )
                WHERE owner_user_id IS NULL
                """
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
