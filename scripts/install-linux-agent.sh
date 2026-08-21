#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${HOME}/.config/devpilot"
STATE_DIR="${HOME}/.local/share/devpilot-linux-agent"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${CONFIG_DIR}/linux-agent.env"
UNIT_FILE="${SYSTEMD_DIR}/devpilot-linux-agent.service"
DEVPILOT_ENV="${ROOT}/.env"

mkdir -p "${CONFIG_DIR}" "${STATE_DIR}" "${SYSTEMD_DIR}" "${ROOT}/runtime"
chmod 700 "${CONFIG_DIR}" "${STATE_DIR}"

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

if ! "${PYTHON}" -c 'import fastapi, uvicorn, httpx' >/dev/null 2>&1; then
  echo "ERRO: dependências do Linux Agent não puderam ser carregadas." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  SECRET="$("${PYTHON}" - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  cat > "${ENV_FILE}" <<EOF
DEVPILOT_LINUX_AGENT_SECRET=${SECRET}
DEVPILOT_LINUX_AGENT_SOCKET=${ROOT}/runtime/linux-agent.sock
DEVPILOT_LINUX_AGENT_HOST=127.0.0.1
DEVPILOT_LINUX_AGENT_PORT=8787
DEVPILOT_LINUX_AGENT_DATA_DIR=${STATE_DIR}
EOF
  chmod 600 "${ENV_FILE}"
else
  SECRET="$(awk -F= '$1=="DEVPILOT_LINUX_AGENT_SECRET"{sub(/^[^=]*=/,"");print;exit}' "${ENV_FILE}")"
fi

if [[ -z "${SECRET}" || "${#SECRET}" -lt 32 ]]; then
  echo "ERRO: segredo do Linux Agent inválido em ${ENV_FILE}" >&2
  exit 1
fi

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

"${PYTHON}" - "${DEVPILOT_ENV}" "${SECRET}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
secret = sys.argv[2]
desired = {
    "DEVPILOT_LINUX_AGENT_SECRET": secret,
    "DEVPILOT_LINUX_AGENT_URL": "http://127.0.0.1:8787",
    "DEVPILOT_LINUX_AGENT_SOCKET": str(path.parent / "runtime" / "linux-agent.sock"),
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
systemctl --user enable --now devpilot-linux-agent.service

echo "DevPilot Linux Agent instalado."
echo "Status: systemctl --user status devpilot-linux-agent.service --no-pager"
echo "O .env do DevPilot foi configurado com o mesmo segredo do Agent."
echo "Se o DevPilot estiver em Docker, recrie o serviço app para carregar o .env atualizado."
