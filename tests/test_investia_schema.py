from sqlalchemy import create_engine, inspect, text

from app.services.schema import ensure_runtime_schema


def test_runtime_schema_upgrades_legacy_investia_publication_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE investia_project_configs (
                    id VARCHAR(36) PRIMARY KEY,
                    status VARCHAR(30),
                    external_project_key VARCHAR(120)
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO investia_project_configs (id, status, external_project_key) "
                "VALUES ('cfg-1', 'draft', 'legacy-project')"
            )
        )

    ensure_runtime_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("investia_project_configs")}
    assert {"public_enabled", "notes", "updated_at"}.issubset(columns)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT public_enabled, notes FROM investia_project_configs WHERE id = 'cfg-1'"
            )
        ).one()

    assert row.public_enabled in (False, 0)
    assert row.notes == ""
