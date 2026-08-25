#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${DEVPILOT_GITHUB_REPO:-a-castilho/devpilot}"
RUNNER_LABEL="${DEVPILOT_RUNNER_LABEL:-devpilot-ci}"
RUNNER_NAME="${DEVPILOT_RUNNER_NAME:-devpilot-$(hostname)}"
RUNNER_DIR="${DEVPILOT_RUNNER_DIR:-$HOME/.local/share/devpilot-actions-runner}"
PID_FILE="$RUNNER_DIR/.runner.pid"
LOG_FILE="$RUNNER_DIR/runner.log"

log() { printf '[devpilot-runner] %s\n' "$*"; }
fail() { log "ERRO: $*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || fail "GitHub CLI (gh) não encontrado."
command -v curl >/dev/null 2>&1 || fail "curl não encontrado."
command -v tar >/dev/null 2>&1 || fail "tar não encontrado."
command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."

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

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    log "Runner já está ativo com PID $old_pid."
  else
    rm -f "$PID_FILE"
  fi
fi

if [[ ! -f "$PID_FILE" ]]; then
  : >"$LOG_FILE"
  nohup ./run.sh >"$LOG_FILE" 2>&1 &
  pid=$!
  printf '%s\n' "$pid" >"$PID_FILE"
  log "Runner iniciado em background com PID $pid."
fi

for _ in {1..20}; do
  status="$(gh api "repos/${REPO}/actions/runners" --jq ".runners[] | select(.name == \"${RUNNER_NAME}\") | .status" 2>/dev/null | head -n1 || true)"
  if [[ "$status" == "online" ]]; then
    log "OK: runner ${RUNNER_NAME} está online."
    log "GitHub Actions agora pode usar a label ${RUNNER_LABEL} sem consumir minutos hospedados."
    log "Log local: $LOG_FILE"
    exit 0
  fi
  sleep 1
done

log "Runner foi iniciado, mas ainda não apareceu online no GitHub."
log "Verifique: tail -n 80 '$LOG_FILE'"
exit 1
