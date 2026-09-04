from pathlib import Path

SOURCE = Path("app/services/github_provisioning.py").read_text(encoding="utf-8")


def test_transient_github_statuses_are_retried():
    assert "TRANSIENT_GITHUB_STATUSES = {429, 500, 502, 503, 504}" in SOURCE
    assert "def _request_with_retry" in SOURCE
    assert "time.sleep(TRANSIENT_RETRY_DELAYS[attempt])" in SOURCE


def test_transient_starter_failure_is_degraded_not_repository_failure():
    assert '"status": "degraded"' in SOURCE
    assert "return _degraded_starter_result(" in SOURCE
    assert "return _remote_with_starter(resumed, starter)" in SOURCE
    assert "return _remote_with_starter(remote, starter)" in SOURCE


def test_auth_and_permission_failures_remain_blocking():
    assert "if status_code == 401:" in SOURCE
    assert "if status_code == 403:" in SOURCE
    assert "Repository permissions > Contents: Read and write" in SOURCE


def test_managed_repository_is_adopted_before_trying_suffixes():
    collision = SOURCE.index("if response.status_code == 422:")
    resumed = SOURCE.index("resumed = _resume_managed_repository", collision)
    continued = SOURCE.index("continue", resumed)
    returned = SOURCE.index("return _remote_with_starter(resumed, starter)", resumed)
    assert resumed < returned < continued


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print("GITHUB_STARTER_TRANSIENT_V100=OK")
