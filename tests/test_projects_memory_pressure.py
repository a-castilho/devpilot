from pathlib import Path


SCRIPT = Path("app/static/product-delivery-ui.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_delivery_cards_use_bounded_concurrency_and_small_cache() -> None:
    text = source()
    assert "CACHE_LIMIT = LOW_POWER ? 12 : 24" in text
    assert "DELIVERY_CONCURRENCY = LOW_POWER ? 2 : 4" in text
    assert "deliveryRequests = new Map()" in text
    assert "while (statusCache.size > CACHE_LIMIT)" in text


def test_delivery_is_lazy_for_project_cards() -> None:
    text = source()
    assert "IntersectionObserver" in text
    assert "viewportObserver.disconnect()" in text
    assert "scheduleDecoration" in text
    assert "Promise.all(items.map((project, index) => decorateCard" not in text


def test_background_refresh_only_touches_visible_projects() -> None:
    text = source()
    assert "refreshVisible(true)" in text
    assert "cardNearViewport" in text
    assert "decorateAll(true)" not in text


def test_delivery_history_has_a_memory_safe_task_cap() -> None:
    text = source()
    assert "HISTORY_TASK_LIMIT = 120" in text
    assert "limit=${HISTORY_TASK_LIMIT}" in text
