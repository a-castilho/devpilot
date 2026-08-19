from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "projects" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("projects")}
    if "organization_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE projects ADD COLUMN organization_id VARCHAR(36)"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_projects_organization_id "
                "ON projects (organization_id)"
            )
        )
