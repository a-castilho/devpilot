from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_command_data_card_is_loaded_after_task_failures():
    main = read("app/main.py")
    failures = main.index('/assets/task-failures.js')
    command_data = main.index('/assets/task-command-data.js')
    assert failures < command_data


def test_command_data_reads_sanitized_raw_log_and_uses_safe_dom_values():
    script = read("app/static/task-command-data.js")
    assert "LOG BRUTO" in script
    assert "command_text" in script
    assert "working_directory" in script
    assert "exit_code" in script
    assert "captured_at" in script
    assert "navigator.clipboard.writeText" in script
    assert "fieldValue.textContent" in script
    assert "eval(" not in script
    assert "new Function" not in script
