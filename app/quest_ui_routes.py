from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["quests-ui"])


@router.get("/quests", response_class=HTMLResponse, include_in_schema=False)
def quest_page():
    return HTMLResponse(
        """<!doctype html>
<html lang=\"pt-BR\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Jornada do Desenvolvimento · DevPilot</title>
<link rel=\"stylesheet\" href=\"/assets/quest-engine.css\">
<style>
html,body{margin:0;min-height:100%;background:#080a0d;color:#eef1f4;font-family:Inter,system-ui,sans-serif}
main{max-width:900px;margin:0 auto;padding:44px 22px}.eyebrow{font-size:.72rem;letter-spacing:.16em;opacity:.55}
h1{font-size:clamp(2rem,5vw,4rem);margin:.2em 0}.lead{max-width:650px;line-height:1.6;opacity:.72}.tower{margin-top:34px;display:grid;gap:8px}
.floor{padding:12px 15px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.025)}
.note{margin-top:26px;font-size:.8rem;opacity:.55}
</style>
</head>
<body>
<main>
<span class=\"eyebrow\">DEV PILOT QUEST ENGINE</span>
<h1>Dos porões à cadeira do administrador.</h1>
<p class=\"lead\">Cada avanço vem de um problema real do DevPilot. Estrelas medem competência, luas marcam complexidade e espadas representam responsabilidade operacional. Progressão técnica nunca concede privilégios de sistema automaticamente.</p>
<div class=\"tower\">
<div class=\"floor\">🏆 Cadeira do Administrador · prova de competência</div>
<div class=\"floor\">⚔ System Administrator · operação e recuperação</div>
<div class=\"floor\">🌙 Architect / DevOps / Security · mudanças de alto risco</div>
<div class=\"floor\">⭐ Developer / Engineer · implementação e testes</div>
<div class=\"floor\">🔎 Porões · observação, investigação e sandbox</div>
</div>
<p class=\"note\">Use o botão “⚔ Jornada” para abrir seu perfil e as missões disponíveis.</p>
</main>
<script src=\"/assets/quest-engine.js\"></script>
</body>
</html>"""
    )
