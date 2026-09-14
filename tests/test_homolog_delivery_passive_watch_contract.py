from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "app/static/game/stable-delivery-url.js"


def test_homolog_delivery_keeps_a_single_lightweight_observer():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "WATCH_MS = 15000" in source
    assert "Continuo acompanhando automaticamente" in source
    assert "document.hidden" in source
    assert "devpilot:delivery:updated" in source
    assert "devpilot:delivery:ready" in source


def test_stable_delivery_surface_does_not_duplicate_delivery_orchestration():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "'/auto'" not in source
    assert "'/start'" not in source
    assert "'/validate-url'" not in source
    assert "MAX_VALIDATIONS" not in source
    assert "RETRY_MS" not in source
    assert "__devpilotEnsureAutomaticDelivery" in source


def run_contract():
    test_homolog_delivery_keeps_a_single_lightweight_observer()
    test_stable_delivery_surface_does_not_duplicate_delivery_orchestration()
    print("HOMOLOG_DELIVERY_PASSIVE_WATCH=OK")


if __name__ == "__main__":
    run_contract()
