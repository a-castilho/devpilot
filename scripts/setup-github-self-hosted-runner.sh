#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${DEVPILOT_GITHUB_REPO:-a-castilho/devpilot}"
RUNNER_LABEL="${DEVPILOT_RUNNER_LABEL:-devpilot-ci}"
RUNNER_NAME="${DEVPILOT_RUNNER_NAME:-devpilot-$(hostname)}"
RUNNER_DIR="${DEVPILOT_RUNNER_DIR:-$HOME/.local/share/devpilot-actions-runner}"
SERVICE_NAME="devpilot-actions-runner.service"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/$SERVICE_NAME"
LOG_FILE="$RUNNER_DIR/runner.log"

log() { printf '[devpilot-runner] %s\n' "$*"; }
fail() { log "ERRO: $*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || fail "GitHub CLI (gh) não encontrado."
command -v curl >/dev/null 2>&1 || fail "curl não encontrado."
command -v tar >/dev/null 2>&1 || fail "tar não encontrado."
command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."
command -v systemctl >/dev/null 2>&1 || fail "systemctl não encontrado; o runner exige supervisão por systemd."

python3 - <<'PY' || exit $?
import sys
if sys.version_info < (3, 12):
    raise SystemExit(
        f"Erro: o runner do DevPilot requer Python 3.12+, encontrado {sys.version.split()[0]} em {sys.executable}"
    )
print(f"[devpilot-runner] Python OK: {sys.executable} ({sys.version.split()[0]})")
PY

gh auth status >/dev/null 2>&1 || fail "gh não está autenticado. Execute gh auth login primeiro."

visibility="$(gh repo view "$REPO" --json visibility --jq '.visibility' 2>/dev/null || true)"
[[ "$visibility" == "PRIVATE" ]] || fail "runner próprio só será configurado para repositório PRIVATE; $REPO retornou ${visibility:-desconhecido}."

case "$(uname -m)" in
  x86_64|amd64) runner_arch="x64" ;;
  aarch64|arm64) runner_arch="arm64" ;;
  *) fail "arquitetura não suportada: $(uname -m)" ;;
esac

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

release_json="$(gh api repos/actions/runner/releases/latest)"
tag="$(printf '%s' "$release_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
version="${tag#v}"
asset="actions-runner-linux-${runner_arch}-${version}.tar.gz"
url="https://github.com/actions/runner/releases/download/${tag}/${asset}"

if [[ ! -x "$RUNNER_DIR/config.sh" ]]; then
  tmp="$(mktemp -p /tmp "${asset}.XXXXXX")"
  trap 'rm -f "${tmp:-}"' EXIT
  log "Baixando GitHub Actions Runner ${tag} para ${runner_arch}..."
  curl -fL --retry 3 --connect-timeout 15 -o "$tmp" "$url"

  digest="$(printf '%s' "$release_json" | python3 -c 'import json,sys; asset=sys.argv[1]; data=json.load(sys.stdin); print(next((item.get("digest") or "" for item in data.get("assets", []) if item.get("name") == asset), ""))' "$asset")"
  if [[ "$digest" == sha256:* ]] && command -v sha256sum >/dev/null 2>&1; then
    expected="${digest#sha256:}"
    actual="$(sha256sum "$tmp" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || fail "checksum do runner não confere."
  fi

  tar -xzf "$tmp" -C "$RUNNER_DIR"
  rm -f "$tmp"
  trap - EXIT
fi

if [[ -f "$RUNNER_DIR/.runner" ]]; then
  log "Runner já configurado em $RUNNER_DIR; mantendo registro existente."
else
  token="$(gh api --method POST "repos/${REPO}/actions/runners/registration-token" --jq '.token')"
  [[ -n "$token" ]] || fail "GitHub não forneceu token de registro. Verifique permissão administrativa do repositório."
  log "Registrando runner ${RUNNER_NAME} com label ${RUNNER_LABEL}..."
  ./config.sh \
    --url "https://github.com/${REPO}" \
    --token "$token" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABEL" \
    --work "_work" \
    --unattended
  unset token
fi

log "Configurando variável DEVPILOT_RUNNER=${RUNNER_LABEL} no repositório..."
gh variable set DEVPILOT_RUNNER --repo "$REPO" --body "$RUNNER_LABEL"

mkdir -p "$SYSTEMD_USER_DIR"
: >"$LOG_FILE"
cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=DevPilot GitHub Actions self-hosted runner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNNER_DIR
ExecStart=$RUNNER_DIR/run.sh
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"

if command -v loginctl >/dev/null 2>&1; then
  linger="$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || true)"
  if [[ "$linger" != "yes" ]]; then
    if loginctl enable-linger "$USER" >/dev/null 2>&1; then
      log "Linger habilitado: o serviço de usuário pode iniciar após reboot sem login interativo."
    else
      log "ATENÇÃO: não foi possível habilitar linger automaticamente; o serviço reinicia sozinho enquanto o gerenciador systemd do usuário estiver ativo."
    fi
  fi
fi

for _ in {1..20}; do
  service_status="$(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || true)"
  github_status="$(gh api "repos/${REPO}/actions/runners" --jq ".runners[] | select(.name == \"${RUNNER_NAME}\") | .status" 2>/dev/null | head -n1 || true)"
  if [[ "$service_status" == "active" && "$github_status" == "online" ]]; then
    log "OK: runner ${RUNNER_NAME} está online e supervisionado por systemd."
    log "Reinício automático: habilitado (${SERVICE_NAME})."
    log "GitHub Actions pode usar a label ${RUNNER_LABEL}."
    log "Log local: $LOG_FILE"
    exit 0
  fi
  sleep 1
done

log "Runner não ficou online dentro do tempo esperado."
log "Serviço: $(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || true)"
log "Verifique: systemctl --user status '$SERVICE_NAME' --no-pager"
log "Log local: $LOG_FILE"
exit 1
