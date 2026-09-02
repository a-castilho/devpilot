from __future__ import annotations

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Padrão não encontrado: {label}")
    return text.replace(old, new, 1)


def patch_frontend_routes() -> None:
    path = "app/frontend_ui_routes.py"
    text = read(path)
    if "def _project_delivery_mode" not in text:
        text = replace_once(
            text,
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport json\n\n",
            "frontend import json",
        )
        helper = '''_WEB_PROJECT_TYPES = {\n    "saas",\n    "hotsite",\n    "landing-page",\n    "personal-site",\n    "portfolio",\n    "institutional-site",\n    "blog-portal",\n    "ecommerce",\n    "docs-site",\n    "admin",\n    "pwa",\n}\n\n\ndef _project_delivery_mode(codex_config: str | None) -> str:\n    """Classify the final artifact without returning the full project config."""\n    try:\n        config = json.loads(codex_config or "{}")\n    except (TypeError, ValueError, json.JSONDecodeError):\n        return "code"\n    if not isinstance(config, dict):\n        return "code"\n\n    blueprint = config.get("project_blueprint")\n    delivery = config.get("delivery")\n    if not isinstance(blueprint, dict):\n        if isinstance(delivery, dict):\n            providers = delivery.get("providers")\n            if isinstance(providers, dict) and isinstance(providers.get("vercel"), dict):\n                return "web"\n        return "code"\n\n    def values(key: str) -> set[str]:\n        raw = blueprint.get(key) or []\n        if isinstance(raw, str):\n            raw = [raw]\n        if not isinstance(raw, list):\n            return set()\n        return {str(item).strip().lower() for item in raw if str(item).strip()}\n\n    project_types = values("project_type")\n    frontend = values("frontend")\n    if project_types.intersection(_WEB_PROJECT_TYPES):\n        return "web"\n    if frontend and not frontend.issubset({"none", "nenhum"}):\n        return "web"\n    if project_types.intersection({"api", "microservices"}):\n        return "service"\n    return "code"\n\n\n'''
        text = replace_once(
            text,
            "def _project_summary(row) -> dict:\n",
            helper + "def _project_summary(row) -> dict:\n",
            "delivery mode helper",
        )
        text = replace_once(
            text,
            '        "status": row.status,\n        "created_at": row.created_at,',
            '        "status": row.status,\n        "delivery_mode": _project_delivery_mode(row.codex_config),\n        "created_at": row.created_at,',
            "project delivery mode summary",
        )
        text = replace_once(
            text,
            "    limit: int = Query(50, ge=1, le=100),\n    include_project_id: str | None = None,",
            "    limit: int = Query(50, ge=1, le=100),\n    offset: int = Query(0, ge=0, le=10_000),\n    include_project_id: str | None = None,",
            "projects pagination input",
        )
        text = replace_once(
            text,
            "        Project.status,\n        Project.created_at,",
            "        Project.status,\n        Project.codex_config,\n        Project.created_at,",
            "project compact columns",
        )
        text = replace_once(
            text,
            "            .order_by(Project.created_at.desc())\n            .limit(limit)",
            "            .order_by(Project.created_at.desc())\n            .offset(offset)\n            .limit(limit)",
            "projects pagination query",
        )
    text = text.replace(
        "    limit: int = Query(24, ge=1, le=50),",
        "    limit: int = Query(80, ge=1, le=100),",
        1,
    )
    write(path, text)


def patch_runtime() -> None:
    path = "app/static/game/runtime.js"
    text = read(path)
    if "currentUser: null" not in text:
        text = replace_once(
            text,
            "  projects: [],\n};",
            "  projects: [],\n  currentUser: null,\n};",
            "runtime current user",
        )
    text = text.replace("/ui/projects?limit=50", "/ui/projects?limit=100")
    text = text.replace("&limit=24`", "&limit=80`")
    write(path, text)


def patch_history_limits() -> None:
    for path in (
        "app/static/game/task-payload-guard.js",
        "app/static/game/delivery-gate.js",
    ):
        write(path, read(path).replace("limit=24", "limit=80"))


def patch_final_summaries() -> None:
    path = "app/static/game/final-delivery-summary.js"
    text = read(path)
    text = text.replace(
        "for (let phase = 1; phase <= 6; phase += 1)",
        "for (let phase = 1; phase <= 7; phase += 1)",
    )
    text = text.replace(
        "const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER);",
        "const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER) || String(task?.title || '').startsWith('[Jogo] Gate');",
    )
    write(path, text)

    path = "app/static/product-delivery-ui.js"
    write(path, read(path).replace("Array.from({length:6}", "Array.from({length:7}"))


def patch_delivery_bonus() -> None:
    path = "app/static/build-game-url-bonus.js"
    text = read(path)
    if "const requiresPublicUrl" not in text:
        text = replace_once(
            text,
            """  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();\n  const normalizedStatus = delivery => String(delivery?.status || 'pending').toLowerCase();\n  const missionDelivered = delivery => normalizedStatus(delivery) === 'ready' && Boolean(safeUrl(delivery?.url));\n  const autoKey = id => `${AUTO_KEY}:${id}`;\n""",
            """  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();\n  const currentProject = () => {\n    const rows = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];\n    return rows.find(project => String(project?.id) === projectId()) || null;\n  };\n  const deliveryMode = () => String(currentProject()?.delivery_mode || 'code').trim().toLowerCase();\n  const requiresPublicUrl = () => deliveryMode() === 'web';\n  const normalizedStatus = delivery => String(delivery?.status || 'pending').toLowerCase();\n  const missionDelivered = delivery => !requiresPublicUrl() || (normalizedStatus(delivery) === 'ready' && Boolean(safeUrl(delivery?.url)));\n  const autoKey = id => `${AUTO_KEY}:${id}`;\n""",
            "architecture delivery identity",
        )
        text = replace_once(
            text,
            """    if (delivered) {\n      panel.dataset.gameMissionDelivered = '1';\n      if (eyebrow) eyebrow.textContent = 'MISSÃO CONCLUÍDA';\n      if (heading) heading.textContent = '🏆 Sistema entregue e URL validada';\n      if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}URL pública validada e pronta para teste.`;\n      return;\n    }\n""",
            """    if (delivered) {\n      panel.dataset.gameMissionDelivered = '1';\n      if (eyebrow) eyebrow.textContent = 'MISSÃO CONCLUÍDA';\n      if (requiresPublicUrl()) {\n        if (heading) heading.textContent = '🏆 Sistema entregue e URL validada';\n        if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}URL pública validada e pronta para teste.`;\n      } else {\n        if (heading) heading.textContent = '🏆 Entrega técnica concluída';\n        if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}Código, testes e evidências da rodada foram concluídos. Publicação externa é opcional para este tipo de projeto.`;\n      }\n      return;\n    }\n""",
            "architecture delivered heading",
        )
        text = replace_once(
            text,
            """    if (missionDelivered(delivery)) {\n      localStorage.removeItem(autoKey(projectId()));\n      host.innerHTML = `\n        <span class=\"eyebrow\">🎁 ENTREGA FINAL CONCLUÍDA</span>\n        <div class=\"build-game-url-bonus-head\">\n          <strong>URL de teste liberada</strong>\n          <span class=\"build-game-url-bonus-state\">PRONTO PARA TESTAR</span>\n        </div>\n        <p>A missão foi concluída porque o ambiente publicado respondeu ao teste real de disponibilidade.</p>\n        <a class=\"build-game-url-value\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">${escapeHtml(url)}</a>\n        <div class=\"build-game-url-actions\"><a class=\"primary\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">Abrir sistema ↗</a></div>\n      `;\n      return;\n    }\n""",
            """    if (missionDelivered(delivery)) {\n      localStorage.removeItem(autoKey(projectId()));\n      if (requiresPublicUrl()) {\n        host.innerHTML = `\n          <span class=\"eyebrow\">🎁 ENTREGA FINAL CONCLUÍDA</span>\n          <div class=\"build-game-url-bonus-head\">\n            <strong>URL de teste liberada</strong>\n            <span class=\"build-game-url-bonus-state\">PRONTO PARA TESTAR</span>\n          </div>\n          <p>A missão foi concluída porque o ambiente publicado respondeu ao teste real de disponibilidade.</p>\n          <a class=\"build-game-url-value\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">${escapeHtml(url)}</a>\n          <div class=\"build-game-url-actions\"><a class=\"primary\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">Abrir sistema ↗</a></div>\n        `;\n      } else {\n        host.innerHTML = `\n          <span class=\"eyebrow\">🎁 ENTREGA DE DESENVOLVIMENTO CONCLUÍDA</span>\n          <div class=\"build-game-url-bonus-head\">\n            <strong>Rodada pronta para continuar o projeto</strong>\n            <span class=\"build-game-url-bonus-state\">CÓDIGO VALIDADO</span>\n          </div>\n          <p>As sete etapas foram aprovadas. Este projeto não exige URL pública para concluir a rodada.</p>\n          ${url ? `<a class=\"build-game-url-value\" href=\"${escapeHtml(url)}\" target=\"_blank\" rel=\"noopener noreferrer\">${escapeHtml(url)}</a>` : ''}\n        `;\n      }\n      return;\n    }\n""",
            "architecture delivery render",
        )
        text = replace_once(
            text,
            """  const automaticDelivery = async (panel, id, delivery) => {\n    let current = delivery || {};\n    let status = normalizedStatus(current);\n""",
            """  const automaticDelivery = async (panel, id, delivery) => {\n    let current = delivery || {};\n    if (!requiresPublicUrl()) return current;\n    let status = normalizedStatus(current);\n""",
            "skip cloud for code delivery",
        )
        text = replace_once(
            text,
            "    host.innerHTML = '<span class=\"eyebrow\">🚀 ENTREGA FINAL</span><strong>Publicando e validando URL real…</strong>';",
            """    host.innerHTML = requiresPublicUrl()\n      ? '<span class=\"eyebrow\">🚀 ENTREGA FINAL</span><strong>Publicando e validando URL real…</strong>'\n      : '<span class=\"eyebrow\">📦 ENTREGA FINAL</span><strong>Consolidando entrega técnica…</strong>';""",
            "delivery hydration copy",
        )
    write(path, text)


def patch_bootstrap() -> None:
    path = "app/static/game/game-bootstrap.js"
    text = read(path)
    text = text.replace("const ASSET_REVISION = 'game-flow-v77-20260902';", "const ASSET_REVISION = 'game-development-v80-20260902';")
    if "'game/development-continuity.js'" not in text:
        text = replace_once(
            text,
            "    'game/objective-controls.js',\n    'game/delivery-gate.js',",
            "    'game/objective-controls.js',\n    'game/development-continuity.js',\n    'game/delivery-gate.js',",
            "continuity entry asset",
        )
    if "Identificação do jogador" not in text:
        text = replace_once(
            text,
            """      if (typeof window.api !== 'function' || !window.__devpilotGameApiReady) throw new Error('Runtime de comunicação indisponível');\n      if (typeof window.loadBuildGame !== 'function' || !window.__devpilotGameControllerV73) throw new Error('Motor do jogo indisponível');\n\n      window.__devpilotGameLoadError = null;\n""",
            """      if (typeof window.api !== 'function' || !window.__devpilotGameApiReady) throw new Error('Runtime de comunicação indisponível');\n      if (typeof window.loadBuildGame !== 'function' || !window.__devpilotGameControllerV73) throw new Error('Motor do jogo indisponível');\n\n      if (window.__devpilotGameState && !window.__devpilotGameState.currentUser) {\n        window.__devpilotGameState.currentUser = await withTimeout(window.api('/auth/me'), 'Identificação do jogador', 6000);\n      }\n      window.__devpilotGameLoadError = null;\n""",
            "standalone current user",
        )
    write(path, text)


def patch_index() -> None:
    path = "app/static/game/index.html"
    text = read(path)
    text = text.replace("game-flow-v77-20260902", "game-development-v80-20260902")
    text = text.replace("data-game-critical-boot-v77", "data-game-critical-boot-v80")
    text = text.replace('data-devpilot-game-version="v77"', 'data-devpilot-game-version="v80"')
    write(path, text)


def patch_tests() -> None:
    path = "tests/test_game_ships_stable_runtime_contract.py"
    text = read(path)
    text = text.replace("/ui/projects?limit=50", "/ui/projects?limit=100")
    text = text.replace('assert "limit=24" in GAME_RUNTIME', 'assert "limit=80" in GAME_RUNTIME')
    write(path, text)

    Path("tests/test_game_development_continuity_v80.py").write_text(
        '''from pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[1]\nCONTINUITY = (ROOT / "app/static/game/development-continuity.js").read_text(encoding="utf-8")\nBOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")\nRUNTIME = (ROOT / "app/static/game/runtime.js").read_text(encoding="utf-8")\nROUTES = (ROOT / "app/frontend_ui_routes.py").read_text(encoding="utf-8")\nSUMMARY = (ROOT / "app/static/game/final-delivery-summary.js").read_text(encoding="utf-8")\nBONUS = (ROOT / "app/static/build-game-url-bonus.js").read_text(encoding="utf-8")\nDELIVERY_UI = (ROOT / "app/static/product-delivery-ui.js").read_text(encoding="utf-8")\n\n\ndef test_game_can_switch_projects_and_resume_existing_work():\n    assert "switchProject(projectId)" in CONTINUITY\n    assert "localStorage.removeItem(MISSION_KEY)" in CONTINUITY\n    assert "repairStaleMission(state)" in CONTINUITY\n    assert "devpilot:game:projects-ready" in CONTINUITY\n    assert "data-game80-project-switch" in CONTINUITY\n\n\ndef test_game_loads_all_projects_in_bounded_pages():\n    assert "offset: int = Query(0" in ROUTES\n    assert ".offset(offset)" in ROUTES\n    assert "PAGE_SIZE = 100" in CONTINUITY\n    assert "MAX_PROJECTS = 1000" in CONTINUITY\n    assert "/ui/projects?limit=${PAGE_SIZE}&offset=${offset}" in CONTINUITY\n\n\ndef test_game_recovers_failed_or_blocked_execution_before_asking_user():\n    assert "/recovery/escalate" in CONTINUITY\n    assert "/recovery/resume" in CONTINUITY\n    assert "/recovery/intervene" in CONTINUITY\n    assert "['failed', 'blocked', 'cancelled', 'canceled']" in CONTINUITY\n    assert "manual_intervention_required" in CONTINUITY\n    assert "Orientar agente e continuar" in CONTINUITY\n\n\ndef test_compact_runtime_keeps_enough_history_after_retries():\n    assert "/ui/projects?limit=100" in RUNTIME\n    assert "limit=80" in RUNTIME\n    assert "limit: int = Query(80, ge=1, le=100)" in ROUTES\n\n\ndef test_delivery_is_compatible_with_web_service_cli_and_automation_projects():\n    assert "_project_delivery_mode" in ROUTES\n    assert 'return "web"' in ROUTES\n    assert 'return "service"' in ROUTES\n    assert 'return "code"' in ROUTES\n    assert "requiresPublicUrl" in BONUS\n    assert "deliveryMode() === 'web'" in BONUS\n    assert "Este projeto não exige URL pública para concluir a rodada." in BONUS\n\n\ndef test_all_seven_phases_are_reported():\n    assert "phase <= 7" in SUMMARY\n    assert "startsWith('[Jogo] Gate')" in SUMMARY\n    assert "Array.from({length:7}" in DELIVERY_UI\n\n\ndef test_v80_is_loaded_after_simple_ui_and_knows_current_user():\n    assert "'game/development-continuity.js'" in BOOT\n    assert BOOT.index("'game/objective-controls.js'") < BOOT.index("'game/development-continuity.js'")\n    assert "window.api('/auth/me')" in BOOT\n    assert "game-development-v80-20260902" in BOOT\n''',
        encoding="utf-8",
    )


def main() -> None:
    patch_frontend_routes()
    patch_runtime()
    patch_history_limits()
    patch_final_summaries()
    patch_delivery_bonus()
    patch_bootstrap()
    patch_index()
    patch_tests()
    print("GAME_V80_PATCH=OK")


if __name__ == "__main__":
    main()
