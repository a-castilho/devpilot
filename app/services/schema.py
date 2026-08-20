from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements: list[str] = []

    if "projects" in tables:
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        if "organization_id" not in project_columns:
            statements.extend(
                [
                    "ALTER TABLE projects ADD COLUMN organization_id VARCHAR(36)",
                    "CREATE INDEX IF NOT EXISTS ix_projects_organization_id ON projects (organization_id)",
                ]
            )

    if "users" in tables:
        statements.extend(
            [
                "UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'admin'",
                "UPDATE users SET role = 'VIEWER' WHERE role = 'user'",
            ]
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
