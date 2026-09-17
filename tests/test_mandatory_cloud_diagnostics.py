from app import mandatory_cloud_reconciler as reconciler


def test_reconciler_diagnostics_expose_block_reason_without_secrets():
    result = reconciler._result_diagnostics({
        "status": "blocked",
        "url": "",
        "blocked_providers": ["render"],
        "failed_provider": "render",
        "delivery_gate": "repair_exhausted",
        "repair_task_status": "blocked",
        "last_error": "render: HTTP 400",
    })

    assert "blocked_providers=render" in result
    assert "failed_provider=render" in result
    assert "gate=repair_exhausted" in result
    assert "repair=blocked" in result
    assert "error=render: HTTP 400" in result


def test_reconciler_diagnostics_are_single_line_and_bounded():
    result = reconciler._result_diagnostics({"last_error": "x\n" + "y" * 1000})

    assert "\n" not in result
    assert len(result) <= 500
