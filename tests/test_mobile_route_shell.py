from pathlib import Path

from app.main import _inject_mobile_scroll_unlock, spa


FEATURE_LOADER = Path("app/static/feature-loader.js")


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


def test_spa_boot_contains_only_core_runtime_and_no_optional_duplicates():
    response = spa("")
    rendered = response.body.decode("utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    # Optional modules must stay out of the initial SPA shell. Loading them here
    # would reintroduce the heavy automatic boot that caused browser freezes.
    for asset in (
        "project-provisioning.js",
        "example-project.js",
        "profile.js",
    ):
        assert f"/assets/{asset}?v=" not in rendered
        assert asset in loader

    # The deterministic authenticated core owns feature activation.
    assert rendered.count("/assets/feature-loader.js?v=") == 1
