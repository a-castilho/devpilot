from __future__ import annotations

import socket
from types import SimpleNamespace
from urllib.parse import urlsplit

from app.services.safe_http_probe import probe_public_https_url


PUBLIC_IP = "93.184.216.34"


def resolver_for(mapping: dict[str, str]):
    def resolve(host, port, *, type, proto):
        assert port == 443
        assert type == socket.SOCK_STREAM
        assert proto == socket.IPPROTO_TCP
        address = mapping.get(host, PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]

    return resolve


class FakeClient:
    def __init__(self, responses, calls, **kwargs):
        self.responses = responses
        self.calls = calls
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        response = self.responses[url]
        return SimpleNamespace(
            status_code=response[0],
            headers=response[1] if len(response) > 1 else {},
        )


def client_factory(responses, calls, captured):
    def factory(**kwargs):
        captured.update(kwargs)
        return FakeClient(responses, calls, **kwargs)

    return factory


def test_public_provider_url_is_probed_without_automatic_redirects_or_env_proxy():
    url = "https://produto.vercel.app/health"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        url,
        timeout_seconds=7.0,
        resolver=resolver_for({"produto.vercel.app": PUBLIC_IP}),
        client_factory=client_factory({url: (200, {})}, calls, captured),
    )

    assert (ok, status) == (True, 200)
    assert [item[0] for item in calls] == [url]
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False


def test_redirect_to_loopback_is_rejected_before_second_request():
    source = "https://produto.vercel.app"
    destination = "http://127.0.0.1:8080/admin"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        source,
        timeout_seconds=7.0,
        resolver=resolver_for({"produto.vercel.app": PUBLIC_IP}),
        client_factory=client_factory(
            {source: (302, {"location": destination})},
            calls,
            captured,
        ),
    )

    assert (ok, status) == (False, 0)
    assert [item[0] for item in calls] == [source]


def test_redirect_to_link_local_dns_is_rejected_before_second_request():
    source = "https://produto.vercel.app"
    destination = "https://metadata.vercel.app/latest"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        source,
        timeout_seconds=7.0,
        resolver=resolver_for(
            {
                "produto.vercel.app": PUBLIC_IP,
                "metadata.vercel.app": "169.254.169.254",
            }
        ),
        client_factory=client_factory(
            {source: (302, {"location": destination})},
            calls,
            captured,
        ),
    )

    assert (ok, status) == (False, 0)
    assert [item[0] for item in calls] == [source]


def test_provider_hostname_resolving_to_private_ip_is_rejected():
    url = "https://produto.onrender.com/health"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        url,
        timeout_seconds=7.0,
        resolver=resolver_for({"produto.onrender.com": "10.20.30.40"}),
        client_factory=client_factory({}, calls, captured),
    )

    assert (ok, status) == (False, 0)
    assert calls == []


def test_redirect_between_allowed_public_provider_hosts_is_followed_manually():
    source = "https://produto.vercel.app"
    destination = "https://produto-main.vercel.app/"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        source,
        timeout_seconds=7.0,
        resolver=resolver_for(
            {
                "produto.vercel.app": PUBLIC_IP,
                "produto-main.vercel.app": PUBLIC_IP,
            }
        ),
        client_factory=client_factory(
            {
                source: (307, {"location": destination}),
                destination: (200, {}),
            },
            calls,
            captured,
        ),
    )

    assert (ok, status) == (True, 200)
    assert [item[0] for item in calls] == [source, destination]


def test_redirect_to_non_provider_host_is_rejected():
    source = "https://produto.vercel.app"
    destination = "https://example.com/internal"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        source,
        timeout_seconds=7.0,
        resolver=resolver_for({"produto.vercel.app": PUBLIC_IP, "example.com": PUBLIC_IP}),
        client_factory=client_factory(
            {source: (302, {"location": destination})},
            calls,
            captured,
        ),
    )

    assert (ok, status) == (False, 0)
    assert [item[0] for item in calls] == [source]


def test_non_default_https_port_is_rejected_without_request():
    url = "https://produto.vercel.app:8443/health"
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        url,
        timeout_seconds=7.0,
        resolver=resolver_for({"produto.vercel.app": PUBLIC_IP}),
        client_factory=client_factory({}, calls, captured),
    )

    assert (ok, status) == (False, 0)
    assert calls == []


def test_redirect_limit_fails_closed():
    urls = [f"https://produto-{index}.vercel.app" for index in range(5)]
    responses = {
        urls[index]: (302, {"location": urls[index + 1]})
        for index in range(4)
    }
    calls = []
    captured = {}

    ok, status = probe_public_https_url(
        urls[0],
        timeout_seconds=7.0,
        max_redirects=3,
        resolver=resolver_for({urlsplit(url).hostname: PUBLIC_IP for url in urls}),
        client_factory=client_factory(responses, calls, captured),
    )

    assert (ok, status) == (False, 302)
    assert [item[0] for item in calls] == urls[:4]
