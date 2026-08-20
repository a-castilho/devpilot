from sqlalchemy import create_engine, text

from app.services.schema import ensure_runtime_schema


def test_runtime_schema_normalizes_legacy_roles():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, role VARCHAR(20))"))
        connection.execute(text("INSERT INTO users (id,role) VALUES ('1','admin'),('2','user')"))

    ensure_runtime_schema(engine)

    with engine.connect() as connection:
        roles = connection.execute(text("SELECT role FROM users ORDER BY id")).scalars().all()
    assert roles == ["SUPER_ADMIN", "VIEWER"]
