from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "app/static/game/stable-delivery-url.js"


def test_homolog_delivery_never_stops_watching_after_active_retries():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "WATCH_MS = 15000" in source
    assert "passiveWatch" in source
    assert "Continuo acompanhando automaticamente" in source
    assert "attempt > MAX_VALIDATIONS" not in source


def test_homolog_preserves_product_repair_flow_during_watch():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "status === 'repairing'" in source
    assert "'/auto'" in source
    assert "MAX_VALIDATIONS = 60" in source
    assert "RETRY_MS = 4000" in source


def run_contract():
    test_homolog_delivery_never_stops_watching_after_active_retries()
    test_homolog_preserves_product_repair_flow_during_watch()
    print("HOMOLOG_DELIVERY_PASSIVE_WATCH=OK")


if __name__ == "__main__":
    run_contract()
