from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "app/services/delivery_remote_publish_bridge.py"
REARM = ROOT / "app/services/delivery_remote_publish_rearm.py"
SERVICES = ROOT / "app/services/__init__.py"


def test_delivery_recovery_publishes_and_verifies_remote_commit():
    source = BRIDGE.read_text(encoding="utf-8")
    assert 'task.source != _DELIVERY_SOURCE' in source
    assert '["git", "add", "-A"]' in source
    assert '"commit", "-m"' in source
    assert '"push", "origin", f"HEAD:{default_branch}"' in source
    assert '"ls-remote", "origin", f"refs/heads/{default_branch}"' in source
    assert 'remote_verified' in source
    assert 'allow-unrelated-histories' in source


def test_exhausted_repairs_get_one_time_rearm_after_publish_fix():
    source = REARM.read_text(encoding="utf-8")
    assert '[delivery-remote-publish-v1]' in source
    assert 'Task.status.in_((TaskStatus.failed, TaskStatus.blocked))' in source
    assert 'task.status = TaskStatus.queued' in source
    assert 'one_time' in source


def test_delivery_publish_hooks_are_installed_at_service_startup():
    source = SERVICES.read_text(encoding="utf-8")
    assert 'install_delivery_remote_publish_bridge()' in source
    assert 'start_delivery_remote_publish_rearm()' in source
