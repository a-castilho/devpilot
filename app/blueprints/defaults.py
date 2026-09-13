from __future__ import annotations

from .domain import BlueprintFile, BlueprintManifest, BlueprintStatus
from .registry import BlueprintRegistry


def builtin_blueprints() -> tuple[BlueprintManifest, ...]:
    return (
        BlueprintManifest(
            slug="backend-fastapi",
            name="Backend FastAPI",
            version="1.0.0",
            description="API Python FastAPI com health check e estrutura mínima validável.",
            kind="backend",
            status=BlueprintStatus.stable,
            stack={"language": "python", "backend": "fastapi"},
            capabilities=("rest-api", "health-check"),
            parameters=("project_name",),
            tags=("python", "fastapi", "api"),
            files=(
                BlueprintFile("README.md", "# {{ project_name }}\n\nProjeto iniciado por blueprint DevPilot.\n"),
                BlueprintFile("app/__init__.py", ""),
                BlueprintFile(
                    "app/main.py",
                    "from fastapi import FastAPI\n\napp = FastAPI(title=\"{{ project_name }}\")\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                ),
            ),
        ),
        BlueprintManifest(
            slug="fullstack-fastapi-react",
            name="Fullstack FastAPI + React",
            version="1.0.0",
            description="Base fullstack com FastAPI e React para SaaS e painéis web.",
            kind="fullstack",
            status=BlueprintStatus.candidate,
            stack={"language": "python", "backend": "fastapi", "frontend": "react"},
            capabilities=("rest-api", "frontend", "health-check"),
            parameters=("project_name",),
            tags=("python", "fastapi", "react", "saas"),
            files=(
                BlueprintFile("README.md", "# {{ project_name }}\n\nFastAPI + React blueprint.\n"),
                BlueprintFile("backend/app/__init__.py", ""),
                BlueprintFile(
                    "backend/app/main.py",
                    "from fastapi import FastAPI\n\napp = FastAPI(title=\"{{ project_name }}\")\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                ),
                BlueprintFile("frontend/src/App.jsx", "export default function App(){ return <main>{{ project_name }}</main>; }\n"),
            ),
        ),
        BlueprintManifest(
            slug="fullstack-fastapi-react-postgres",
            name="Fullstack FastAPI + React + PostgreSQL",
            version="1.0.0",
            description="Base SaaS com FastAPI, React, PostgreSQL e Docker Compose.",
            kind="fullstack",
            status=BlueprintStatus.candidate,
            stack={"language": "python", "backend": "fastapi", "frontend": "react", "database": "postgresql"},
            capabilities=("rest-api", "frontend", "database", "docker", "health-check"),
            parameters=("project_name", "database_name"),
            tags=("python", "fastapi", "react", "postgresql", "docker", "saas"),
            files=(
                BlueprintFile("README.md", "# {{ project_name }}\n\nFastAPI + React + PostgreSQL blueprint.\n"),
                BlueprintFile(
                    "docker-compose.yml",
                    "services:\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_DB: {{ database_name }}\n      POSTGRES_USER: app\n      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}\n",
                ),
                BlueprintFile("backend/app/__init__.py", ""),
                BlueprintFile(
                    "backend/app/main.py",
                    "from fastapi import FastAPI\n\napp = FastAPI(title=\"{{ project_name }}\")\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                ),
                BlueprintFile("frontend/src/App.jsx", "export default function App(){ return <main>{{ project_name }}</main>; }\n"),
            ),
        ),
    )


def install_builtin_blueprints(registry: BlueprintRegistry) -> None:
    for manifest in builtin_blueprints():
        try:
            registry.register(manifest)
        except FileExistsError:
            pass
