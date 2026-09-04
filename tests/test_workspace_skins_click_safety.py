from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "app/static/workspace-skins.js").read_text(encoding="utf-8")


def test_workspace_skins_never_installs_global_feature_gate():
    assert "FEATURE_BUNDLES" not in RUNTIME
    assert "featureTrigger(" not in RUNTIME
    assert "installFeatureGate(" not in RUNTIME
    assert "stopImmediatePropagation" not in RUNTIME
    assert "event.preventDefault()" not in RUNTIME


def test_workspace_skins_never_overrides_browser_append_child():
    assert "body.appendChild =" not in RUNTIME
    assert "__devpilotNativeBodyAppend" not in RUNTIME
    assert "installDeferredCircuitBreaker" not in RUNTIME


def test_workspace_skins_is_visual_only():
    assert "workspace-skin-picker" in RUNTIME
    assert "workspace-skins.css" in RUNTIME
    assert "__devpilotWorkspaceSkinsReady = true" in RUNTIME
