from app.main import (
    _authenticated_script_loader,
    _strip_pre_auth_heavy_scripts,
    _unique_authenticated_scripts,
    spa,
)


def test_pre_auth_html_keeps_only_boot_scripts():
    html = """
    <body>
      <script src="/assets/app.js" defer></script>
      <script src="/assets/project-ships.js?v=1" defer></script>
      <script src="/assets/build-game-cockpit.js?v=1" defer></script>
    </body>
    """
    result = _strip_pre_auth_heavy_scripts(html)
    assert '/assets/app.js' in result
    assert '/assets/project-ships.js' not in result
    assert '/assets/build-game-cockpit.js' not in result


def test_authenticated_loader_is_token_gated_and_sequential():
    loader = _authenticated_script_loader()
    assert "localStorage.getItem('devpilot-token')" in loader
    assert "script.async = false" in loader
    assert "script.onload = loadNext" in loader
    assert "script.onerror = loadNext" in loader
    assert "devpilot:authenticated-ui-ready" in loader


def test_authenticated_script_list_is_deduplicated():
    scripts = _unique_authenticated_scripts()
    assert len(scripts) == len(set(scripts))
    assert "project-provisioning.js" in scripts
    assert "build-game-cockpit.js" in scripts
    assert "mission-control.js" in scripts


def test_spa_does_not_boot_heavy_scripts_before_authentication():
    response = spa("")
    html = response.body.decode("utf-8")
    assert '<script src="/assets/app.js?v=' in html
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/build-game-cockpit.js' not in html
    assert '<script src="/assets/project-ships.js' not in html
    assert "localStorage.getItem('devpilot-token')" in html
