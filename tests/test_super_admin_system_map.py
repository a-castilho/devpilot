from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Workspace
from app.super_admin_voice_routes import system_map_dashboard


def test_system_map_dashboard_returns_serializable_nodes_for_empty_workspace():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            db.add(Workspace(name="DevPilot", slug="default"))
            db.commit()
            payload = system_map_dashboard(db)

        encoded = jsonable_encoder(payload)
        nodes = {node["id"]: node for node in encoded["nodes"]}

        assert encoded["summary"]["users"] == 0
        assert nodes["api"]["target_view"] is None
        assert nodes["auth"]["target_view"] is None
        assert nodes["database"]["target_view"] is None
        assert nodes["linux"]["target_view"] is None
    finally:
        engine.dispose()
