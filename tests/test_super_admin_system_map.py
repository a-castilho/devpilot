from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Workspace
from app.super_admin_voice_routes import system_map_dashboard


def test_system_map_builds_and_serializes_with_default_workspace():
    """Regression: Python payload must use None, never the JavaScript literal null."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)

    with Session(test_engine) as db:
        db.add(Workspace(name="Default", slug="default"))
        db.commit()

        payload = system_map_dashboard(db)
        encoded = jsonable_encoder(payload)

    assert encoded["nodes"]
    assert encoded["edges"]
    assert encoded["flow"]
    assert any(node["id"] == "api" and node["target_view"] is None for node in encoded["nodes"])
    assert any(node["id"] == "database" and node["target_view"] is None for node in encoded["nodes"])
    assert any(node["id"] == "linux" and node["target_view"] is None for node in encoded["nodes"])
