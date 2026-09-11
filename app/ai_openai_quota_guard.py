from __future__ import annotations

import httpx


def _quota_exhausted(metadata: dict) -> bool:
    text = " ".join(
        str(metadata.get(key) or "").lower()
        for key in ("error_code", "error_type", "message")
    )
    return any(
        fragment in text
        for fragment in (
            "credit_balance_exhausted",
            "insufficient_quota",
            "billing_hard_limit",
            "billing limit",
            "quota exceeded",
            "exceeded your current quota",
            "no credits remaining",
        )
    )


def install_openai_quota_guard() -> None:
    from app import chat_mode_routes, voice_all_provider_routes
    from app.voice_all_provider_routes import (
        _attempt,
        _provider_api_keys,
        _provider_error_metadata,
        _response_text,
        _stored_provider_models,
    )
    from app.voice_conversation_routes import _chat_models

    async def guarded_try_openai_all(
        client: httpx.AsyncClient,
        db,
        workspace_id: str,
        input_text: str,
        instructions: str,
    ):
        attempts: list[dict] = []
        keys = _provider_api_keys(db, workspace_id, "openai")
        if not keys:
            return None, [_attempt("openai", "", status=0, error_code="not_configured")]

        models = list(
            dict.fromkeys(
                [
                    *_stored_provider_models(db, workspace_id, "openai"),
                    *_chat_models(),
                ]
            )
        )

        for api_key in keys:
            for model in models:
                try:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "instructions": instructions,
                            "input": input_text,
                            "max_output_tokens": 280,
                            "store": False,
                        },
                    )
                except httpx.HTTPError as error:
                    attempts.append(
                        _attempt(
                            "openai",
                            model,
                            status=502,
                            error_type=type(error).__name__,
                            error_code="network_error",
                        )
                    )
                    break

                if response.status_code >= 400:
                    metadata = _provider_error_metadata(response)
                    attempts.append(_attempt("openai", model, **metadata))
                    # Saldo/cota pertence à conta/chave, não ao modelo. Não bombardear
                    # a API tentando todos os modelos quando a primeira resposta já
                    # prova que nenhum deles poderá funcionar com esta chave.
                    if _quota_exhausted(metadata):
                        break
                    # 401/403 também são falhas da credencial, não do modelo.
                    if response.status_code in {401, 403}:
                        break
                    continue

                try:
                    data = response.json()
                except ValueError:
                    attempts.append(
                        _attempt("openai", model, status=502, error_code="invalid_json")
                    )
                    continue

                answer = _response_text(data)
                if not answer:
                    attempts.append(
                        _attempt("openai", model, status=502, error_code="empty_response")
                    )
                    continue

                usage = data.get("usage")
                return {
                    "answer": answer,
                    "provider": "openai",
                    "model": model,
                    "usage": usage if isinstance(usage, dict) else {},
                }, attempts
            else:
                continue
            # Interrompe este provider quando a chave está sem saldo ou inválida.
            if attempts:
                last = attempts[-1]
                if _quota_exhausted(last) or int(last.get("status") or 0) in {401, 403}:
                    continue

        return None, attempts

    voice_all_provider_routes._try_openai_all = guarded_try_openai_all
    chat_mode_routes._try_openai_all = guarded_try_openai_all


install_openai_quota_guard()
