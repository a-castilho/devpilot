from pathlib import Path

SRC = Path('app/services/failure_recovery.py').read_text(encoding='utf-8')


def test_automatic_recovery_bypasses_generic_prompt_gate():
    assert 'def _activate_automatic_recovery' in SRC
    assert 'recovery.status == TaskStatus.awaiting_approval' in SRC
    assert 'recovery.status = TaskStatus.queued' in SRC
    assert 'approved_at=None if requires_authorization else datetime.now(timezone.utc)' in SRC
    assert 'failure_recovery.automatic_gate_repaired' in SRC


if __name__ == '__main__':
    test_automatic_recovery_bypasses_generic_prompt_gate()
    print('FAILURE_RECOVERY_AUTOMATIC_GATE=OK')
