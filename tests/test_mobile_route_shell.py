from app.main import _inject_mobile_scroll_unlock, spa


def test_scroll_unlock_injection_uses_real_newline():
    html = "<html><head></head><body></body></html>"
    rendered = _inject_mobile_scroll_unlock(html)

    assert "mobile-scroll-unlock.css" in rendered
    assert "\\n</head>" not in rendered


def test_mobile_route_gets_forced_mobile_shell():
    response = spa("mobile")
    rendered = response.body.decode("utf-8")

    assert '<body class="mobile-route">' in rendered
    assert "/assets/mobile-route.css?v=" in rendered
    assert "\\n</head>" not in rendered
    assert "\\n</body>" not in rendered


def test_regular_route_keeps_desktop_shell():
    response = spa("reports")
    rendered = response.body.decode("utf-8")

    assert '<body class="mobile-route">' not in rendered
    assert "/assets/mobile-route.css?v=" not in rendered
