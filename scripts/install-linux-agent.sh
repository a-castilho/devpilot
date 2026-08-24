#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${HOME}/.config/devpilot"
STATE_DIR="${HOME}/.local/share/devpilot-linux-agent"
AGENT_RUNTIME_DIR="${STATE_DIR}/runtime"
SOCKET_PATH="${AGENT_RUNTIME_DIR}/agent.sock"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${CONFIG_DIR}/linux-agent.env"
UNIT_FILE="${SYSTEMD_DIR}/devpilot-linux-agent.service"
DEVPILOT_ENV="${ROOT}/.env"
TERMINAL_USER="${DEVPILOT_LINUX_TERMINAL_USER:-devpilot}"
TERMINAL_LAUNCHER="/usr/local/libexec/devpilot-terminal-shell"
SERVICE_USER="$(id -un)"
SUDOERS_FILE="/etc/sudoers.d/devpilot-linux-agent-${SERVICE_USER}"

if [[ ! "${TERMINAL_USER}" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
  echo "ERRO: nome de usuário Linux dedicado inválido: ${TERMINAL_USER}" >&2
  exit 1
fi

require_sudo() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "ERRO: sudo é necessário para provisionar o usuário Linux dedicado do DevPilot." >&2
    exit 1
  fi
  sudo -v
}

provision_terminal_user() {
  local created=0
  local terminal_home
  local launcher_tmp
  local sudoers_tmp
  local visudo_bin

  require_sudo

  if ! getent passwd "${TERMINAL_USER}" >/dev/null 2>&1; then
    echo "Criando usuário Linux dedicado '${TERMINAL_USER}'..."
    sudo useradd \
      --create-home \
      --shell /bin/bash \
      --comment "DevPilot isolated Linux terminal" \
      "${TERMINAL_USER}"
    sudo passwd -l "${TERMINAL_USER}" >/dev/null 2>&1 || true
    created=1
  fi

  terminal_home="$(getent passwd "${TERMINAL_USER}" | awk -F: '{print $6; exit}')"
  if [[ -z "${terminal_home}" || "${terminal_home}" == "/" ]]; then
    echo "ERRO: HOME inválida para o usuário dedicado ${TERMINAL_USER}." >&2
    exit 1
  fi

  sudo -u "${TERMINAL_USER}" mkdir -p "${terminal_home}/Documents"

  launcher_tmp="$(mktemp)"
  cat >"${launcher_tmp}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-${HOME}}"
cd -- "${TARGET}"
exec /bin/bash -i
EOF
  sudo install -d -o root -g root -m 755 "$(dirname "${TERMINAL_LAUNCHER}")"
  sudo install -o root -g root -m 755 "${launcher_tmp}" "${TERMINAL_LAUNCHER}"
  rm -f "${launcher_tmp}"

  # O Agent executa somente o launcher fixo como o usuário menos privilegiado.
  # SETENV é necessário apenas para preservar as variáveis Git/GitHub que o
  # próprio backend injeta a partir da credencial criptografada em Clouds.
  sudoers_tmp="$(mktemp)"
  printf '%s ALL=(%s) NOPASSWD:SETENV: %s\n' \
    "${SERVICE_USER}" "${TERMINAL_USER}" "${TERMINAL_LAUNCHER}" \
    >"${sudoers_tmp}"
  chmod 600 "${sudoers_tmp}"
  visudo_bin="$(command -v visudo || true)"
  if [[ -z "${visudo_bin}" ]]; then
    rm -f "${sudoers_tmp}"
    echo "ERRO: visudo não encontrado; não é seguro instalar a regra sudoers." >&2
    exit 1
  fi
  sudo "${visudo_bin}" -cf "${sudoers_tmp}" >/dev/null
  sudo install -o root -g root -m 440 "${sudoers_tmp}" "${SUDOERS_FILE}"
  rm -f "${sudoers_tmp}"

  if ! sudo -n -H -u "${TERMINAL_USER}" -- "${TERMINAL_LAUNCHER}" "${terminal_home}" \
      </dev/null >/dev/null 2>&1; then
    echo "ERRO: não foi possível iniciar o launcher como ${TERMINAL_USER}." >&2
    exit 1
  fi

  if [[ "${created}" == "1" ]]; then
    echo "Usuário '${TERMINAL_USER}' criado com senha bloqueada e HOME ${terminal_home}."
  else
    echo "Usuário dedicado '${TERMINAL_USER}' já existe; configuração preservada."
  fi
}

provision_terminal_user

mkdir -p "${CONFIG_DIR}" "${STATE_DIR}" "${AGENT_RUNTIME_DIR}" "${SYSTEMD_DIR}"
chmod 700 "${CONFIG_DIR}" "${STATE_DIR}"
chmod 755 "${AGENT_RUNTIME_DIR}"

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

rm -f "${SOCKET_PATH}" 2>/dev/null || true
rm -f "${ROOT}/runtime/linux-agent.sock" 2>/dev/null || true
rm -f "${ROOT}/runtime/linux-agent/agent.sock" 2>/dev/null || true

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
DEVPILOT_LINUX_TERMINAL_USER=${TERMINAL_USER}
DEVPILOT_LINUX_TERMINAL_LAUNCHER=${TERMINAL_LAUNCHER}
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
UMask=0000
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
  if "${PYTHON}" - "${SOCKET_PATH}" "${TERMINAL_USER}" <<'PY' >/dev/null 2>&1
import sys
import httpx

socket_path = sys.argv[1]
terminal_user = sys.argv[2]
transport = httpx.HTTPTransport(uds=socket_path)
with httpx.Client(transport=transport, base_url="http://devpilot-agent", timeout=1.0) as client:
    response = client.get("/health")
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise SystemExit(1)
    account = payload.get("terminal_user") or {}
    if account.get("username") != terminal_user or not account.get("ready"):
        raise SystemExit(1)
PY
  then
    healthy=1
    break
  fi
  sleep 0.2
done

if [[ "${healthy}" != "1" ]]; then
  echo "ERRO: Linux Agent não ficou saudável após a instalação do usuário dedicado." >&2
  systemctl --user status devpilot-linux-agent.service --no-pager >&2 || true
  echo "=== ÚLTIMOS LOGS ===" >&2
  journalctl --user -u devpilot-linux-agent.service -n 60 --no-pager >&2 || true
  exit 1
fi

chmod 666 "${SOCKET_PATH}" 2>/dev/null || true

echo "DevPilot Linux Agent instalado e saudável."
echo "Usuário das sessões diretas: ${TERMINAL_USER}"
echo "Socket: ${SOCKET_PATH}"
echo "Status: systemctl --user status devpilot-linux-agent.service --no-pager"
echo "O usuário do seu terminal não é reutilizado pelas sessões diretas do DevPilot."
echo "GitHub do terminal usa a credencial cadastrada em Clouds quando disponível."
echo "O .env do DevPilot foi configurado com o mesmo segredo do Agent."
echo "Se o DevPilot estiver em Docker, recrie o serviço app para carregar o .env atualizado."
