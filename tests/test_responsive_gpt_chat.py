from pathlib import Path


CSS = Path("app/static/mission-control-ai-dashboard.css")


def test_ai_chat_uses_responsive_gpt_workspace_modes():
    css = CSS.read_text(encoding="utf-8")

    assert "body.mc-ai-open .shell main" in css
    assert "margin-right:446px" in css
    assert "@media (min-width:721px) and (max-width:1279px)" in css
    assert "body.mc-ai-open::before" in css
    assert "html.sidebar-collapsed .mc-ai-drawer" in css
    assert "@media (max-width:720px)" in css


def test_ai_chat_keeps_mobile_touch_targets_and_readable_input():
    css = CSS.read_text(encoding="utf-8")

    mobile = css.rsplit("@media (max-width:720px)", 1)[1]
    assert ".mc-ai-modes button{min-height:40px}" in mobile
    assert ".mc-ai-composer textarea{min-height:44px;font-size:16px}" in mobile
    assert "grid-template-rows:auto auto minmax(0,1fr) auto auto" in mobile
