import json
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:8080"


def fetch(path: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_localhost_health_and_frontend_are_live():
    status, body = fetch("/health")
    assert status == 200
    payload = json.loads(body.decode("utf-8"))
    assert payload.get("status") == "ok"
    assert payload.get("service") == "devpilot"

    status, body = fetch("/")
    assert status == 200
    assert b"DevPilot" in body


def test_localhost_serves_chat_voice_stability_assets():
    status, loader = fetch("/assets/feature-loader.js")
    assert status == 200
    assert b"voice-runtime-stability.js" in loader

    status, voice = fetch("/assets/voice-runtime-stability.js")
    assert status == 200
    assert b"response.status === 422" in voice

    status, watchdog = fetch("/assets/chat-request-watchdog.js")
    assert status == 200
    assert b"45000" in watchdog or b"45" in watchdog


def test_localhost_chat_and_transcription_routes_are_protected_and_reachable():
    status, _ = fetch(
        "/api/chat",
        method="POST",
        data=b'{"transcript":"ping","mode":"planning","response_style":"chat","history":[]}',
        headers={"Content-Type": "application/json"},
    )
    assert status in {401, 403}

    status, _ = fetch("/api/voice/transcriptions", method="POST", data=b"")
    assert status in {401, 403}
