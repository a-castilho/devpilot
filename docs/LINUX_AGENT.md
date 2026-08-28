# DevPilot Linux Agent

O Linux Agent conecta o DevPilot ao sistema Linux local sem executar shell dentro do backend web.

## Arquitetura

1. O usuário entra no DevPilot com autenticação normal.
2. As rotas `/api/linux/*` aplicam o controle de acesso do perfil autenticado.
3. O backend assina cada chamada ao Agent com HMAC-SHA256, timestamp e nonce.
4. O Agent valida assinatura, janela temporal e replay.
5. O Agent abre uma sessão PTY persistente usando o usuário Linux que iniciou o serviço.
6. O transcript do terminal e os metadados da sessão ficam em `~/.local/share/devpilot-linux-agent/sessions/`.

O terminal é livre: `cd`, pipes, redirecionamentos, Git, Docker e demais comandos disponíveis ao usuário Linux funcionam dentro da mesma sessão. O Agent não executa como root automaticamente.

## Instalação local

Execute:

```bash
bash scripts/install-linux-agent.sh
```

O instalador cria:

- `~/.config/devpilot/linux-agent.env` com segredo de 48 bytes;
- `~/.config/systemd/user/devpilot-linux-agent.service`;
- diretório de estado `~/.local/share/devpilot-linux-agent`;
- variáveis equivalentes no `.env` do DevPilot.

O instalador usa por padrão o Unix Domain Socket `runtime/linux-agent.sock`. O fallback TCP continua disponível em `127.0.0.1:8787` quando o socket não é configurado.

## Docker

O `docker-compose.yml` monta `./runtime` em `/runtime` e aponta o backend para `/runtime/linux-agent.sock`. Assim o container conversa com o Agent sem abrir uma porta de shell na LAN.

Depois da primeira instalação ou de trocar o segredo:

```bash
docker compose up -d --force-recreate app worker
```

## Auditoria assinada pelo usuário Linux

A trilha de auditoria do DevPilot continua encadeada por `previous_hash` e `event_hash`, mas eventos novos podem receber uma atestação Ed25519 emitida pelo Linux Agent.

Na primeira assinatura, o Agent cria a identidade em:

```text
~/.devpilot/identity/
├── audit-private.key   # 0600; nunca sai do usuário Linux
└── audit-public.key    # chave pública usada para verificação
```

A assinatura inclui a identidade efetiva observada pelo kernel no processo do Agent: `username`, `uid`, `euid`, `gid`, `egid` e `hostname`. O backend recebe somente a chave pública, o identificador da chave, a assinatura e esses metadados. A chave privada não é enviada ao banco nem à aplicação web.

A prova criptográfica fica no campo `details._linux_audit` do próprio `AuditEvent`, preservando a tabela e os registros históricos. Eventos anteriores permanecem verificáveis pelo algoritmo legado. Se o Agent estiver configurado mas indisponível, o registro deixa isso explícito como `status=unavailable` em vez de inventar uma assinatura.

Os endpoints externos de verificação são:

- `GET /api/audit/linux-identity` — mostra qual identidade Linux está assinando;
- `GET /api/audit/integrity` — verifica encadeamento, hashes e assinaturas e informa se toda a cadeia está assinada pelo Linux.

A identidade representa o usuário Linux **real que executa aquela instância do Agent**. Se uma instalação de produção utilizar contas Linux distintas por usuário, cada conta deve executar sua própria instância/socket do Agent para que as assinaturas permaneçam separadas por identidade do sistema operacional.

## Segurança

- UI/API: acesso ao módulo Linux respeita o perfil autenticado e o isolamento configurado no backend.
- Backend -> Agent: HMAC-SHA256 com corpo, método, path/query, timestamp e nonce.
- Replay: nonces recentes são rejeitados.
- Transporte: Unix Domain Socket local por padrão; TCP `127.0.0.1` existe apenas como fallback.
- Auditoria: eventos são encadeados por hash e, com o Agent configurado, assinados com Ed25519 pela identidade Linux efetiva.
- Terminal: para não duplicar senhas em banco, a entrada é registrada por tamanho + SHA-256; o transcript integral permanece no host.
- Processo: comandos recebem exatamente as permissões do usuário Linux do serviço. O Agent não adiciona `sudo` nem roda como root.

## Endpoints internos do Agent

- `GET /health`
- `GET /v1/system`
- `GET /v1/audit/identity`
- `POST /v1/audit/attest`
- `GET /v1/terminal/sessions`
- `POST /v1/terminal/sessions`
- `GET /v1/terminal/sessions/{id}/output`
- `POST /v1/terminal/sessions/{id}/input`
- `POST /v1/terminal/sessions/{id}/resize`
- `DELETE /v1/terminal/sessions/{id}`

Com exceção de `/health`, todos exigem assinatura HMAC.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

