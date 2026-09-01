# GitHub Actions Runner — supervisão e alerta

## Objetivo

O DevPilot usa um runner self-hosted com a label `devpilot-ci` para executar a esteira de CI sem depender de runner hospedado. Esse runner é infraestrutura crítica: quando fica offline, workflows permanecem aguardando e PRs podem ficar bloqueadas sem erro de código.

A implementação mantém duas garantias complementares:

1. **recuperação automática** por um serviço `systemd --user`;
2. **visibilidade operacional** no painel `Super Admin · Sistema`.

## Serviço supervisionado

O script `scripts/setup-github-self-hosted-runner.sh` instala/configura o GitHub Actions Runner e cria o serviço de usuário:

```text
devpilot-actions-runner.service
```

Características:

- `Restart=always`;
- `RestartSec=5`;
- `systemctl --user enable --now`;
- tentativa de habilitar `loginctl enable-linger` para permitir inicialização após reboot sem login interativo;
- log local em `~/.local/share/devpilot-actions-runner/runner.log`;
- não usa `nohup` nem mantém PID manual como fonte de verdade.

Se `linger` não puder ser habilitado sem privilégio adicional, o instalador não oculta o problema: emite aviso. O runner ainda reinicia automaticamente enquanto o gerenciador systemd do usuário estiver ativo.

## Estado exposto ao DevPilot

`app/services/runner_status.py` consulta o serviço usando argumentos fixos para `systemctl --user`, timeout curto e saída capturada. Nenhuma credencial ou variável sensível é retornada.

O endpoint protegido para `SUPER_ADMIN` é:

```text
GET /api/voice/runner-status
```

Resposta conceitual:

```json
{
  "status": "online | offline | unknown",
  "online": true,
  "service_enabled": true,
  "service": "devpilot-actions-runner.service",
  "label": "devpilot-ci",
  "detail": "..."
}
```

`online` significa que o serviço supervisionado está `active` no host do DevPilot. O instalador também valida, no momento da configuração, se o GitHub enxerga o runner como `online`.

## Avisos no Super Admin

Ao abrir ou atualizar `Super Admin · Sistema`, o frontend consulta em paralelo:

- `/api/super-admin/voice/system-map`;
- `/api/voice/runner-status`.

O painel reutiliza a área de avisos já existente. Os estados tratados são:

- `offline`: **GitHub Actions Runner devpilot-ci offline — CI e PRs podem permanecer aguardando.**
- `unknown`: informa que o estado não pôde ser confirmado naquele host;
- `online` com `service_enabled=false`: informa que o processo está ativo, mas o reinício automático não está habilitado;
- `online` e habilitado: nenhum alerta de runner é exibido.

Assim, o aviso desaparece automaticamente quando a saúde volta ao normal e o painel é atualizado.

## Instalação / atualização

A partir da raiz do projeto:

```bash
bash scripts/setup-github-self-hosted-runner.sh
```

A execução é idempotente: se o runner já estiver registrado, o script preserva o registro e atualiza a supervisão do serviço.

## Diagnóstico

Estado do serviço:

```bash
systemctl --user status devpilot-actions-runner.service --no-pager
```

Log do runner:

```bash
tail -n 100 ~/.local/share/devpilot-actions-runner/runner.log
```

Estado de inicialização automática:

```bash
systemctl --user is-enabled devpilot-actions-runner.service
```

Linger do usuário:

```bash
loginctl show-user "$USER" -p Linger
```

## Segurança

- O painel não recebe token GitHub, registration token, PAT, segredo de ambiente ou comando arbitrário.
- O backend não executa shell string; usa `subprocess.run` com lista fixa de argumentos e timeout.
- O endpoint exige `SUPER_ADMIN` além da autenticação normal do router.
- A supervisão não altera política de aprovação, branch protection ou gates de CI.
- Um runner offline continua bloqueando a entrega; o alerta apenas explica o estado e o serviço tenta recuperar o processo.

## Testes

`tests/test_runner_supervision.py` cobre:

- serviço ativo e habilitado;
- serviço offline;
- ausência de `nohup` no instalador;
- `Restart=always` e `enable --now`;
- integração do aviso no mapa do Super Admin;
- proteção do endpoint por `SUPER_ADMIN`.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

