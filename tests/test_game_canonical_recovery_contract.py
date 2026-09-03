from pathlib import Path

SRC = Path('app/static/game/recovery-runtime.js').read_text(encoding='utf-8')


def test_game_uses_backend_recovery_only():
    assert '/recovery/${action}' in SRC
    assert "'escalate'" in SRC
    assert 'Backend/worker is the only recovery owner' in SRC
    assert 'originalRetry()' in SRC  # verifier/non-failure fallback only
    assert "runtimeState === 'archived'" not in SRC
    assert '[Jogo] Correção etapa' not in SRC


if __name__ == '__main__':
    test_game_uses_backend_recovery_only()
    print('GAME_CANONICAL_RECOVERY=OK')
