from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CSS = (ROOT / "app/static/layout-adaptive-v15.css").read_text(encoding="utf-8")
JS = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "app/static/runtime-experience-v13.js").read_text(encoding="utf-8")


def validate() -> None:
    assert "container-type: inline-size" in CSS
    assert "@container dp-view" in CSS
    assert "@container dp-builder-view" in CSS
    assert "repeat(auto-fit" in CSS
    assert "#tasks-view .tasks-v9-details-panel" in CSS
    assert "#project-builder-form.project-builder" in CSS
    assert "#super-admin-system-view .system-map-columns" in CSS
    assert "width: 100vw !important" in CSS

    assert "__devpilotViewportAdaptiveV15" in JS
    assert "dp-zoom-out" in JS
    assert "dp-space-compact" in JS
    assert "dp-space-short" in JS
    assert "visualViewport" in JS
    assert "screen?.availWidth" in JS
    assert "--dp-ui-boost" in JS

    assert "viewport-adaptive-v15.js" in RUNTIME
    assert "loadAdaptiveV15" in RUNTIME


if __name__ == "__main__":
    validate()
    print("CONTAINER QUERIES: OK")
    print("ZOOM REDUZIDO: OK")
    print("MONITOR BAIXO: OK")
    print("TASKS FULL WIDTH: OK")
    print("PROJECT BUILDER ADAPTATIVO: OK")
    print("SUPER ADMIN ADAPTATIVO: OK")
    print("MOBILE FULL WIDTH: OK")
