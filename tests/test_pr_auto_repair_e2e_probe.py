from app.pr_auto_repair_probe import answer


def test_pr_auto_repair_e2e_probe() -> None:
    assert answer() == 42
