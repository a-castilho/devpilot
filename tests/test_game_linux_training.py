from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "app" / "static" / "game-linux-training.js"
MAIN = ROOT / "app" / "main.py"


def test_linux_training_is_loaded_with_the_game():
    source = MAIN.read_text(encoding="utf-8")
    assert 'build-game.js' in source
    assert 'game-linux-training.js' in source
    assert source.index('build-game.js') < source.index('game-linux-training.js')


def test_linux_training_is_scoped_to_game_and_does_not_touch_super_admin_linux_view():
    source = TRAINING.read_text(encoding="utf-8")
    assert "#build-game-view" in source
    assert "#linux-view" not in source
    assert "nav-super-admin" not in source
    assert "/api/super-admin" not in source
    assert "data-view=\"linux\"" not in source


def test_linux_training_uses_only_guided_first_steps_commands():
    source = TRAINING.read_text(encoding="utf-8")
    assert "command: 'pwd'" in source
    assert "command: 'ls -lah'" in source
    assert "cd ~/Documents" in source
    assert "git status --short --branch" in source
    assert "<textarea" not in source
    assert "data-game-linux-training-step" in source


def test_linux_training_uses_authenticated_terminal_sessions_and_real_exit_evidence():
    source = TRAINING.read_text(encoding="utf-8")
    assert "/api/linux/terminal/sessions" in source
    assert "Authorization: `Bearer ${token()}`" in source
    assert "__dp_training_status=$?" in source
    assert "exitCode !== 0" in source
    assert "devpilot:game-training-progress" in source
