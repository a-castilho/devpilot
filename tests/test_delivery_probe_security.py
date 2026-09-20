from app import delivery_cloud_bridge as cloud_bridge
from app import delivery_url_recovery as recovery


def test_cloud_bridge_probe_uses_safe_public_probe(monkeypatch):
    captured = {}

    def fake_probe(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return True, 204

    monkeypatch.setattr(cloud_bridge, "probe_public_https_url", fake_probe)

    assert cloud_bridge._probe("https://api.onrender.com/health") == (True, 204)
    assert captured["url"] == "https://api.onrender.com/health"
    assert captured["timeout_seconds"] == 12.0
    assert captured["accept"] == "application/json,text/html,*/*"


def test_delivery_recovery_probe_uses_safe_public_probe(monkeypatch):
    captured = {}

    def fake_probe(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return True, 200

    monkeypatch.setattr(recovery, "probe_public_https_url", fake_probe)

    assert recovery._probe_public_url("https://produto.vercel.app") == (True, 200)
    assert captured == {
        "url": "https://produto.vercel.app",
        "timeout_seconds": 7.0,
    }


def test_public_url_parser_rejects_credentials_and_nonstandard_port():
    assert recovery._safe_public_url("https://user:pass@produto.vercel.app") == ""
    assert recovery._safe_public_url("https://produto.vercel.app:8443") == ""
    assert recovery._safe_public_url("https://produto.vercel.app./") == ""
