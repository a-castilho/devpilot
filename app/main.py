from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.agentos.apps_router import router as agentos_apps_router
from app.agentos.intelligence_router import router as agentos_intelligence_router
from app.agentos.router import router as agentos_router
from app.api import router
from app.db import Base, engine


STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="DevPilot API", version="1.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(agentos_router)
app.include_router(agentos_apps_router)
app.include_router(agentos_intelligence_router)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/health")
def health():
    return {"status": "ok", "service": "devpilot", "version": "1.1.0"}


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    candidate = STATIC / path
    return FileResponse(candidate if path and candidate.is_file() else STATIC / "index.html")
