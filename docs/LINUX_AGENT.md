# DevPilot Linux Agent

O Linux Agent conecta o DevPilot ao sistema Linux local sem executar shell dentro do backend web.

## Arquitetura

1. O usuário entra no DevPilot com autenticação normal.
2. As rotas `/api/linux/*` exigem `SUPER_ADMIN`.
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

## Segurança

- UI: o módulo Linux só é criado para `SUPER_ADMIN`.
- API: toda rota `/api/linux/*` valida `SUPER_ADMIN`; esconder a tela não é a barreira de segurança.
- Backend -> Agent: HMAC-SHA256 com corpo, método, path/query, timestamp e nonce.
- Replay: nonces recentes são rejeitados.
- Transporte: Unix Domain Socket local por padrão; TCP `127.0.0.1` existe apenas como fallback.
- Auditoria: abertura, entrada e encerramento da sessão entram na cadeia de auditoria do DevPilot. Para não duplicar senhas em banco, a entrada é registrada por tamanho + SHA-256; o transcript integral permanece no host.
- Processo: comandos recebem exatamente as permissões do usuário Linux do serviço. O Agent não adiciona `sudo` nem roda como root.

## Endpoints internos do Agent

- `GET /health`
- `GET /v1/system`
- `GET /v1/terminal/sessions`
- `POST /v1/terminal/sessions`
- `GET /v1/terminal/sessions/{id}/output`
- `POST /v1/terminal/sessions/{id}/input`
- `POST /v1/terminal/sessions/{id}/resize`
- `DELETE /v1/terminal/sessions/{id}`

Com exceção de `/health`, todos exigem assinatura HMAC.
