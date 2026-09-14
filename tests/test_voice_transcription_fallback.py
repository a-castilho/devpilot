import asyncio
import json

import httpx

from app.voice_transcription_routes import (
    _google_response_data,
    _provider_error,
    _transcribe_google,
)


def test_google_response_data_extracts_transcription():
    response = httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "atualizar"},
                            {"text": "DevPilot local"},
                        ]
                    }
                }
            ]
        },
    )

    text, usage = _google_response_data(response)

    assert text == "atualizar DevPilot local"
    assert usage == {}


def test_google_response_data_preserves_provider_usage():
    response = httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": "teste concluído"}]}}
            ],
            "usageMetadata": {
                "promptTokenCount": 229,
                "candidatesTokenCount": 3,
                "totalTokenCount": 334,
            },
        },
    )

    text, usage = _google_response_data(response)

    assert text == "teste concluído"
    assert usage["totalTokenCount"] == 334


def test_google_response_data_supports_direct_text_envelope():
    response = httpx.Response(200, json={"output_text": "comando reconhecido"})

    text, usage = _google_response_data(response)

    assert text == "comando reconhecido"
    assert usage == {}


def test_provider_error_preserves_quota_signal():
    error = _provider_error("openai", [429])

    assert error.status_code == 429
    assert error.provider == "openai"


def test_google_fallback_transcribes_audio():
    async def run():
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-goog-api-key"] == "google-test-key"
            assert "gemini-2.5-flash" in str(request.url)
            body = json.loads(request.content.decode("utf-8"))
            inline = body["contents"][0]["parts"][1]["inlineData"]
            assert inline["mimeType"] == "audio/webm"
            assert inline["data"]
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "iniciar projeto devpilot"}]
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 100,
                        "candidatesTokenCount": 4,
                        "totalTokenCount": 140,
                    },
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await _transcribe_google(
                client,
                payload=b"fake-audio",
                content_type="audio/webm",
                api_keys=["google-test-key"],
                models=["gemini-2.5-flash"],
            )

    text, model, usage = asyncio.run(run())

    assert text == "iniciar projeto devpilot"
    assert model == "gemini-2.5-flash"
    assert usage["totalTokenCount"] == 140
