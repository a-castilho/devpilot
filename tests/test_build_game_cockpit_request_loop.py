from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "app" / "static" / "build-game-cockpit.js"
TOKEN_USAGE_MOBILE_FIX = ROOT / "app" / "static" / "token-usage-mobile-fix.js"


def source() -> str:
    return COCKPIT.read_text(encoding="utf-8")


def request_guard_source() -> str:
    return TOKEN_USAGE_MOBILE_FIX.read_text(encoding="utf-8")


def test_linux_wallet_refresh_is_coalesced_per_project_context():
    text = source()
    assert "const linuxRefreshInFlight = new Map();" in text
    assert "const pending = linuxRefreshInFlight.get(requestKey);" in text
    assert "if (pending) return pending;" in text
    assert "linuxRefreshInFlight.set(requestKey, request);" in text
    assert "linuxRefreshInFlight.delete(requestKey);" in text


def test_existing_cockpit_does_not_refetch_when_wallet_is_already_rendered():
    text = source()
    guarded = "if (existing) {\n      if (!shell.querySelector('[data-linux-wallet]')) void refreshLinuxEconomy(view);\n      return;\n    }"
    assert guarded in text
    assert "if (existing) {\n      void refreshLinuxEconomy(view);" not in text


def test_identical_wallet_state_does_not_mutate_dom_again():
    text = source()
    assert "linuxWalletFingerprint" in text
    assert "if (existingWallet?.dataset.linuxWalletFingerprint === fingerprint) return;" in text
    assert "wallet.dataset.linuxWalletFingerprint = fingerprint;" in text


def test_task_collection_reads_are_coalesced_and_short_cached():
    text = request_guard_source()
    assert "const taskReadsInFlight = new Map();" in text
    assert "const taskReadCache = new Map();" in text
    assert "const pending = taskReadsInFlight.get(requestKey);" in text
    assert "if (pending) return pending;" in text
    assert "taskReadCache.set(requestKey, {savedAt: Date.now(), data});" in text
    assert "const TASK_GET_TTL_MS = 5000;" in text


def test_task_mutations_invalidate_task_read_cache():
    text = request_guard_source()
    assert "method !== 'GET'" in text
    assert "clearTaskReadCache();" in text
    assert "improvedApi.__devpilotTaskReadCoalescing = true;" in text
