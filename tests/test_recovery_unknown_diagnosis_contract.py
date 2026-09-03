from pathlib import Path


def test_unknown_failure_is_diagnosis_not_authorization():
    source = Path('app/services/recovery.py').read_text(encoding='utf-8')
    assert 'status="diagnosis_required"' in source
    assert 'strategy="diagnose_original_error"' in source
    assert 'requires_authorization=False' in source
    assert 'isso não significa falta de autorização' in source
    assert 'def _safe_error(self, value: str, limit: int = 2400)' in source
    assert '[contexto reduzido]' in source


if __name__ == '__main__':
    test_unknown_failure_is_diagnosis_not_authorization()
    print('RECOVERY_UNKNOWN_DIAGNOSIS=OK')
