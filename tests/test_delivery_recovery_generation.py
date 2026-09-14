from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATION = ROOT / "app/services/delivery_recovery_generation.py"
REARM = ROOT / "app/services/delivery_remote_publish_rearm.py"
SERVICES = ROOT / "app/services/__init__.py"


def test_new_generation_does_not_inherit_legacy_retry_markers():
    from app.services.delivery_recovery_generation import (
        reset_for_new_generation,
        retry_count_for_current_generation,
    )

    legacy = "base\n[delivery-repair-retry:1]\n[delivery-repair-retry:2]\n[delivery-repair-retry:3]\n"
    fresh = reset_for_new_generation(legacy, 2)
    assert "[delivery-recovery-generation:2]" in fresh
    assert "[delivery-repair-retry:" not in fresh
    assert retry_count_for_current_generation(fresh) == 0


def test_generation_patch_preserves_last_failure_details():
    source = GENERATION.read_text(encoding="utf-8")
    assert 'state["last_failure"]' in source
    assert 'state["last_error"] = failure.get("message")' in source
    assert 'delivery_remote_publish' in source


def test_rearm_v2_resets_legacy_retries_once():
    source = REARM.read_text(encoding="utf-8")
    assert '[delivery-remote-publish-v2]' in source
    assert 'reset_for_new_generation' in source
    assert 'legacy_retries_reset' in source


def test_generation_patch_is_installed_before_rearm_startup():
    source = SERVICES.read_text(encoding="utf-8")
    assert 'install_delivery_recovery_generation_patch()' in source
    assert source.index('install_delivery_recovery_generation_patch()') < source.index('start_delivery_remote_publish_rearm()')
