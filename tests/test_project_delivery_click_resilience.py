from pathlib import Path


SCRIPT = Path("app/static/product-delivery-ui.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_projects_observer_is_not_subtree_recursive() -> None:
    text = source()
    assert "hostObserver.observe(host, {childList:true});" in text
    assert "observer.observe(view, {childList:true, subtree:true})" not in text


def test_project_actions_use_delegated_clicks() -> None:
    text = source()
    assert "installDelegatedClicks" in text
    assert "data-project-create-sticky" in text
    assert "data-delivery-history" in text
    assert "data-delivery-action" in text
    assert "document.addEventListener('click'" in text


def test_delivery_markup_skips_identical_rerender() -> None:
    text = source()
    assert "box.dataset.deliveryMarkup !== markup" in text
    assert "box.dataset.deliveryMarkup = markup" in text
