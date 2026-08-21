#!/usr/bin/env bash
set -Eeuo pipefail

# DevPilot low-RAM optimizer: measure first, change one service at a time,
# and always restore temporary tests before returning.

CANDIDATES=(
  "cups.service"
  "cups-browsed.service"
  "bluetooth.service"
  "ModemManager.service"
  "avahi-daemon.service"
  "whoopsie.service"
)

PROTECTED=(
  "NetworkManager.service"
  "dbus.service"
  "systemd-logind.service"
  "systemd-resolved.service"
  "docker.service"
  "containerd.service"
  "ssh.service"
)

REPORT_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/devpilot/low-ram"
mkdir -p "$REPORT_DIR"

usage() {
  cat <<'EOF'
Uso:
  scripts/low-ram-safe.sh audit
  scripts/low-ram-safe.sh test-all
  scripts/low-ram-safe.sh test <servico.service>
  scripts/low-ram-safe.sh apply <servico.service> --confirm
  scripts/low-ram-safe.sh rollback <servico.service>

Regras:
  - audit não altera o sistema.
  - test/test-all param temporariamente um serviço e SEMPRE o restauram.
  - apply só aceita serviços da lista segura e exige --confirm.
  - serviços de rede, sessão, Docker e resolução são protegidos.
EOF
}

is_in_array() {
  local needle="$1"; shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

require_candidate() {
  local service="$1"
  if is_in_array "$service" "${PROTECTED[@]}"; then
    echo "BLOQUEADO: $service é protegido e não será alterado." >&2
    exit 2
  fi
  if ! is_in_array "$service" "${CANDIDATES[@]}"; then
    echo "BLOQUEADO: $service não está na lista segura de candidatos." >&2
    echo "Candidatos: ${CANDIDATES[*]}" >&2
    exit 2
  fi
}

mem_available_kb() {
  awk '/MemAvailable:/ {print $2}' /proc/meminfo
}

swap_used_kb() {
  awk '
    /SwapTotal:/ {total=$2}
    /SwapFree:/ {free=$2}
    END {print total-free}
  ' /proc/meminfo
}

service_memory_kb() {
  local service="$1"
  local control_group
  control_group="$(systemctl show "$service" -p ControlGroup --value 2>/dev/null || true)"
  [[ -n "$control_group" && "$control_group" != "/" ]] || { echo 0; return; }

  local cgroup="/sys/fs/cgroup${control_group}"
  if [[ -r "$cgroup/memory.current" ]]; then
    awk '{printf "%d\n", $1/1024}' "$cgroup/memory.current"
    return
  fi

  local total=0 pid rss
  while read -r pid; do
    [[ -r "/proc/$pid/status" ]] || continue
    rss="$(awk '/VmRSS:/ {print $2}' "/proc/$pid/status" 2>/dev/null || echo 0)"
    total=$((total + ${rss:-0}))
  done < <(systemctl show "$service" -p MainPID --value 2>/dev/null | awk '$1 > 0')
  echo "$total"
}

service_exists() {
  systemctl cat "$1" >/dev/null 2>&1
}

service_active() {
  systemctl is-active --quiet "$1"
}

service_enabled_state() {
  systemctl is-enabled "$1" 2>/dev/null || true
}

check_network() {
  ip route show default | grep -q '^default '
}

check_dns() {
  getent ahosts github.com >/dev/null 2>&1
}

check_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! systemctl is-active --quiet docker.service 2>/dev/null; then
    return 0
  fi
  docker info >/dev/null 2>&1
}

check_devpilot() {
  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi
  if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1; then
    return 0
  fi
  # If the local app is not currently listening, do not classify that as a regression.
  ! ss -ltn 2>/dev/null | grep -q ':8080 '
}

check_audio() {
  if command -v pactl >/dev/null 2>&1; then
    pactl info >/dev/null 2>&1
  else
    return 0
  fi
}

health_check() {
  local failures=0
  check_network || { echo "  ✗ rota de rede"; failures=$((failures+1)); }
  check_dns || { echo "  ✗ DNS"; failures=$((failures+1)); }
  check_docker || { echo "  ✗ Docker"; failures=$((failures+1)); }
  check_devpilot || { echo "  ✗ DevPilot :8080"; failures=$((failures+1)); }
  check_audio || { echo "  ✗ áudio"; failures=$((failures+1)); }
  if (( failures == 0 )); then
    echo "  ✓ rede, DNS, Docker, DevPilot e áudio preservados"
    return 0
  fi
  return 1
}

print_snapshot() {
  echo "=== MEMÓRIA ==="
  free -h
  echo
  echo "=== TOP 20 PROCESSOS POR RAM ==="
  ps -eo pid,comm,rss,%mem --sort=-rss | head -n 21
  echo
  echo "=== CANDIDATOS ==="
  local service
  for service in "${CANDIDATES[@]}"; do
    if service_exists "$service"; then
      printf '%-24s active=%-8s enabled=%-10s mem=%s KiB\n' \
        "$service" \
        "$(systemctl is-active "$service" 2>/dev/null || true)" \
        "$(service_enabled_state "$service")" \
        "$(service_memory_kb "$service")"
    fi
  done
  echo
  echo "=== SAÚDE ==="
  health_check || true
}

audit() {
  local report="$REPORT_DIR/audit-$(date +%Y%m%d-%H%M%S).txt"
  print_snapshot | tee "$report"
  echo
  echo "Relatório: $report"
}

test_service() {
  local service="$1"
  require_candidate "$service"

  if ! service_exists "$service"; then
    echo "IGNORADO: $service não existe neste sistema."
    return 0
  fi
  if ! service_active "$service"; then
    echo "IGNORADO: $service já está inativo."
    return 0
  fi

  local before_mem before_swap service_mem after_mem after_swap gained_kb swap_delta_kb
  before_mem="$(mem_available_kb)"
  before_swap="$(swap_used_kb)"
  service_mem="$(service_memory_kb "$service")"

  echo "TESTE TEMPORÁRIO: $service"
  echo "  memória do serviço antes: ${service_mem} KiB"
  echo "  parando temporariamente..."

  local restored=0
  restore() {
    if (( restored == 0 )); then
      sudo systemctl start "$service" >/dev/null 2>&1 || true
      restored=1
    fi
  }
  trap restore EXIT INT TERM

  sudo systemctl stop "$service"
  sleep 2

  after_mem="$(mem_available_kb)"
  after_swap="$(swap_used_kb)"
  gained_kb=$((after_mem - before_mem))
  swap_delta_kb=$((before_swap - after_swap))

  echo "  RAM disponível antes: ${before_mem} KiB"
  echo "  RAM disponível depois: ${after_mem} KiB"
  echo "  variação observada: ${gained_kb} KiB"
  echo "  variação de swap usada: ${swap_delta_kb} KiB"
  echo "  checando funcionalidades críticas..."

  if health_check; then
    echo "  RESULTADO: teste funcional aprovado."
  else
    echo "  RESULTADO: regressão detectada; NÃO aplicar." >&2
  fi

  echo "  restaurando $service..."
  restore
  trap - EXIT INT TERM
  sleep 1

  if service_active "$service"; then
    echo "  ✓ serviço restaurado"
  else
    echo "  ✗ falha ao restaurar $service" >&2
    return 1
  fi
}

test_all() {
  local service
  for service in "${CANDIDATES[@]}"; do
    echo
    echo "============================================================"
    test_service "$service" || true
  done
}

apply_service() {
  local service="$1"
  local confirmation="${2:-}"
  require_candidate "$service"
  [[ "$confirmation" == "--confirm" ]] || {
    echo "Aplicação persistente exige --confirm." >&2
    exit 2
  }
  service_exists "$service" || { echo "$service não existe." >&2; exit 2; }

  echo "Aplicando otimização persistente em $service..."
  sudo systemctl disable --now "$service"
  sleep 2

  if health_check; then
    echo "✓ $service desativado e verificações críticas aprovadas."
    echo "Rollback: scripts/low-ram-safe.sh rollback $service"
  else
    echo "Falha funcional detectada. Revertendo imediatamente..." >&2
    sudo systemctl enable --now "$service" || sudo systemctl start "$service"
    exit 1
  fi
}

rollback_service() {
  local service="$1"
  require_candidate "$service"
  service_exists "$service" || { echo "$service não existe." >&2; exit 2; }
  sudo systemctl enable --now "$service" 2>/dev/null || sudo systemctl start "$service"
  echo "✓ $service restaurado."
}

main() {
  local command="${1:-}"
  case "$command" in
    audit)
      audit
      ;;
    test-all)
      test_all
      ;;
    test)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      test_service "$2"
      ;;
    apply)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      apply_service "$2" "${3:-}"
      ;;
    rollback)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      rollback_service "$2"
      ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"
