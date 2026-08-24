#!/usr/bin/env python3
"""Smoke test HTTP opcionalmente autenticado.

Variáveis:
  TEST_BASE_URL       URL base (padrão: http://127.0.0.1:8080)
  TEST_PATHS          GETs separados por vírgula (padrão: /health,/)
  TEST_LOGIN_PATH     endpoint de login opcional
  TEST_EMAIL          e-mail opcional
  TEST_PASSWORD       senha opcional
  TEST_TOKEN_FIELD    campo do token (padrão: access_token)
  TEST_TIMEOUT        timeout em segundos (padrão: 20)

Se login/e-mail/senha forem informados, o token Bearer é usado nos GETs.
Credenciais não são persistidas. O processo retorna 0 somente se todos passarem.
"""
from __future__ import annotations
import json
import os
import sys
from urllib import error, request

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
PATHS = [p.strip() for p in os.getenv("TEST_PATHS", "/health,/").split(",") if p.strip()]
LOGIN = os.getenv("TEST_LOGIN_PATH", "").strip()
EMAIL = os.getenv("TEST_EMAIL", "").strip()
PASSWORD = os.getenv("TEST_PASSWORD", "")
TOKEN_FIELD = os.getenv("TEST_TOKEN_FIELD", "access_token")
TIMEOUT = float(os.getenv("TEST_TIMEOUT", "20"))


def call(method: str, path: str, token: str = "", payload=None):
    url = path if path.startswith("http://") or path.startswith("https://") else f"{BASE}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status, res.read().decode("utf-8", "replace")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def main() -> int:
    print(f"Smoke test -> {BASE}")
    failures = 0
    token = ""
    if LOGIN or EMAIL or PASSWORD:
        if not (LOGIN and EMAIL and PASSWORD):
            print("❌ Autenticação incompleta: defina TEST_LOGIN_PATH, TEST_EMAIL e TEST_PASSWORD.")
            return 2
        try:
            status, body = call("POST", LOGIN, payload={"email": EMAIL, "password": PASSWORD})
            obj = json.loads(body or "{}")
            token = str(obj.get(TOKEN_FIELD, ""))
            ok = 200 <= status < 300 and bool(token)
        except Exception as exc:
            status, ok, body = 0, False, str(exc)
        print(f"{'✅' if ok else '❌'} Login: HTTP {status}")
        failures += 0 if ok else 1
        if not ok:
            return 1
    for path in PATHS:
        try:
            status, body = call("GET", path, token=token)
            ok = 200 <= status < 400
            detail = "OK" if ok else body[:160].replace("\n", " ")
        except Exception as exc:
            status, ok, detail = 0, False, str(exc)
        print(f"{'✅' if ok else '❌'} {path}: HTTP {status} - {detail}")
        failures += 0 if ok else 1
    print(f"Resultado: {'APROVADO' if not failures else 'FALHOU'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
