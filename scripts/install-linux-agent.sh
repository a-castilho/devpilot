#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${HOME}/.config/devpilot"
STATE_DIR="${HOME}/.local/share/devpilot-linux-agent"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${CONFIG_DIR}/linux-agent.env"
UNIT_FILE="${SYSTEMD_DIR}/devpilot-linux-agent.service"
DEVPILOT_ENV="${ROOT}/.env"
RUNTIME_ROOT="${ROOT}/runtime"
AGENT_RUNTIME_DIR="${RUNTIME_ROOT}/linux-agent"
SOCKET_PATH="${AGENT_RUNTIME_DIR}/agent.sock"

mkdir -p "${CONFIG_DIR}" "${STATE_DIR}" "${SYSTEMD_DIR}"
chmod 700 "${CONFIG_DIR}" "${STATE_DIR}"

# Stop a previous crash-loop before changing its runtime/socket configuration.
systemctl --user stop devpilot-linux-agent.service >/dev/null 2>&1 || true

SYSTEM_PYTHON="$(command -v python3 || true)"
if [[ -z "${SYSTEM_PYTHON}" ]]; then
  echo "ERRO: python3 não encontrado no Linux." >&2
  exit 1
fi

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
elif "${SYSTEM_PYTHON}" -c 'import fastapi, uvicorn, httpx' >/dev/null 2>&1; then
  PYTHON="${SYSTEM_PYTHON}"
else
  if ! "${SYSTEM_PYTHON}" -m venv "${ROOT}/.venv"; then
    echo "ERRO: não foi possível criar ${ROOT}/.venv. Instale o pacote python3-venv e execute novamente." >&2
    exit 1
  fi
  PYTHON="${ROOT}/.venv/bin/python"
fi

if ! "${PYTHON}" -c 'import fastapi, uvicorn, httpx' >/dev/null 2>&1; then
  "${PYTHON}" -m pip install --upgrade pip
  "${PYTHON}" -m pip install -e "${ROOT}"
fi

if ! "${PYTHON}" -c 'import fastapi, uvicorn, httpx; from app.linux_agent.main import app' >/dev/null 2>&1; then
  echo "ERRO: dependências/código do Linux Agent não puderam ser carregados por ${PYTHON}." >&2
  "${PYTHON}" -c 'from app.linux_agent.main import app' || true
  exit 1
fi

prepare_agent_runtime() {
  # Docker may previously have created ./runtime as root. Keep the Agent socket
  # in a dedicated user-owned directory instead of making all runtime world-writable.
  mkdir -p "${AGENT_RUNTIME_DIR}" 2>/dev/null || true
  if [[ -d "${AGENT_RUNTIME_DIR}" && -w "${AGENT_RUNTIME_DIR}" ]]; then
    chmod 755 "${AGENT_RUNTIME_DIR}" 2>/dev/null || true
    return 0
  fi

  if command -v docker >/dev/null 2>&1; then
    mkdir -p "${RUNTIME_ROOT}" 2>/dev/null || true
    local uid gid
    uid="$(id -u)"
    gid="$(id -g)"
    echo "Reparando permissão do runtime do Linux Agent via Docker..."
    docker run --rm \
      -v "${RUNTIME_ROOT}:/runtime" \
      alpine:3.20 \
      sh -c "mkdir -p /runtime/linux-agent && chown ${uid}:${gid} /runtime/linux-agent && chmod 755 /runtime/linux-agent"
  fi

  if [[ ! -d "${AGENT_RUNTIME_DIR}" || ! -w "${AGENT_RUNTIME_DIR}" ]]; then
    echo "ERRO: ${AGENT_RUNTIME_DIR} não é gravável pelo usuário $(id -un)." >&2
    echo "Proprietário atual:" >&2
    ls -ld "${RUNTIME_ROOT}" "${AGENT_RUNTIME_DIR}" 2>/dev/null >&2 || true
    echo "Corrija a propriedade/permissão desse diretório e execute novamente." >&2
    exit 1
  fi
}

prepare_agent_runtime
rm -f "${SOCKET_PATH}" 2>/dev/null || true
# Remove the old v1 socket when possible; it is no longer used.
rm -f "${RUNTIME_ROOT}/linux-agent.sock" 2>/dev/null || true

if [[ -f "${ENV_FILE}" ]]; then
  SECRET="$(awk -F= '$1=="DEVPILOT_LINUX_AGENT_SECRET"{sub(/^[^=]*=/,"");print;exit}' "${ENV_FILE}")"
else
  SECRET=""
fi

if [[ -z "${SECRET}" || "${#SECRET}" -lt 32 ]]; then
  SECRET="$("${PYTHON}" - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
fi

cat > "${ENV_FILE}" <<EOF
DEVPILOT_LINUX_AGENT_SECRET=${SECRET}
DEVPILOT_LINUX_AGENT_SOCKET=${SOCKET_PATH}
DEVPILOT_LINUX_AGENT_HOST=127.0.0.1
DEVPILOT_LINUX_AGENT_PORT=8787
DEVPILOT_LINUX_AGENT_DATA_DIR=${STATE_DIR}
EOF
chmod 600 "${ENV_FILE}"

cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=DevPilot Linux Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON} -m app.linux_agent
Restart=on-failure
RestartSec=2
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=default.target
EOF

"${PYTHON}" - "${DEVPILOT_ENV}" "${SECRET}" "${SOCKET_PATH}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
secret = sys.argv[2]
socket_path = sys.argv[3]
desired = {
    "DEVPILOT_LINUX_AGENT_SECRET": secret,
    "DEVPILOT_LINUX_AGENT_URL": "http://127.0.0.1:8787",
    "DEVPILOT_LINUX_AGENT_SOCKET": socket_path,
    "DEVPILOT_LINUX_AGENT_TIMEOUT_SECONDS": "5",
}
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
seen = set()
result = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
    if key in desired:
        result.append(f"{key}={desired[key]}")
        seen.add(key)
    else:
        result.append(line)
for key, value in desired.items():
    if key not in seen:
        result.append(f"{key}={value}")
path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
PY
chmod 600 "${DEVPILOT_ENV}" || true

systemctl --user daemon-reload
systemctl --user enable devpilot-linux-agent.service >/dev/null
systemctl --user restart devpilot-linux-agent.service

healthy=0
for _ in $(seq 1 30); do
  if "${PYTHON}" - "${SOCKET_PATH}" <<'PY' >/dev/null 2>&1
import sys
import httpx

socket_path = sys.argv[1]
transport = httpx.HTTPTransport(uds=socket_path)
with httpx.Client(transport=transport, base_url="http://devpilot-agent", timeout=1.0) as client:
    response = client.get("/health")
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise SystemExit(1)
PY
  then
    healthy=1
    break
  fi
  sleep 0.2
done

if [[ "${healthy}" != "1" ]]; then
  echo "ERRO: Linux Agent não ficou saudável após a instalação." >&2
  systemctl --user status devpilot-linux-agent.service --no-pager >&2 || true
  echo "=== ÚLTIMOS LOGS ===" >&2
  journalctl --user -u devpilot-linux-agent.service -n 60 --no-pager >&2 || true
  exit 1
fi

echo "DevPilot Linux Agent instalado e saudável."
echo "Socket: ${SOCKET_PATH}"
echo "Status: systemctl --user status devpilot-linux-agent.service --no-pager"
echo "O .env do DevPilot foi configurado com o mesmo segredo do Agent."
echo "Se o DevPilot estiver em Docker, recrie o serviço app para carregar o .env atualizado."
