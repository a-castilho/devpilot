# DevPilot — seu desenvolvedor

DevPilot é um SaaS leve para automatizar desenvolvimento de software por dashboard, API
ou voz. Ele organiza múltiplos projetos e tarefas, aplica instruções `AGENTS.md`, controla
configurações do Codex, executa trabalho em branches isoladas e registra cada decisão em
uma trilha de auditoria encadeada por hash.

## O que o MVP entrega

- dashboard responsivo/PWA para desktop e celular;
- projetos com URL Git, branch, `AGENTS.md` e perfil Codex;
- tarefas vindas do dashboard, voz ou API;
- fila persistente e worker independente;
- aprovação humana para ações de risco;
- executor Codex com `subprocess` sem shell e timeout;
- vault criptografado para múltiplos provedores de IA;
- auditoria de comandos, configuração, aprovação e execução;
- política de hosts Git permitidos e isolamento de diretórios;
- Docker Compose com aplicação, worker e PostgreSQL;
- SQLite para desenvolvimento local sem infraestrutura adicional.

## Arquitetura

```text
PWA responsiva
   │ texto / voz / aprovação
FastAPI ── política ── auditoria hash-chain
   │                    │
PostgreSQL/SQLite       vault criptografado
   │
worker ── projeto isolado ── Codex CLI ── Git branch/PR
```

O MVP usa voz encadeada: reconhecimento no dispositivo, transcrição revisável, interpretação,
aprovação e execução. Isso mantém o comando auditável. Uma evolução natural é substituir a
captura pelo OpenAI Realtime via WebRTC, usando credenciais efêmeras emitidas pelo backend.

## Executar localmente

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8080
```

Em outro terminal:

```bash
source .venv/bin/activate
python -m app.worker
```

Abra `http://localhost:8080` e use o valor de `DEVPILOT_BOOTSTRAP_TOKEN` para entrar.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Antes de produção, gere uma chave Fernet e configure `DEVPILOT_ENCRYPTION_KEY`:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Mantenha `DEVPILOT_EXECUTION_ENABLED=false` até o host do worker ter Codex CLI e Git
configurados, credenciais de escopo mínimo e diretório isolado.

### Iniciar projetos Docker automaticamente na máquina de desenvolvimento

O gerenciador local inicia apenas projetos explicitamente autorizados. Isso evita executar
automaticamente um `compose.yaml` recebido de um repositório não confiável.

```bash
python tools/docker_projects.py register ~/Documents/devpilot
python tools/docker_projects.py sync --root ~/Documents
python tools/docker_projects.py install --root ~/Documents
```

O último comando instala um serviço `systemd --user`, iniciado junto com a sessão do usuário.
Cada projeto recebe um nome Compose isolado. Portas publicadas continuam sendo definidas pelo
próprio projeto; uma colisão é registrada como falha, sem alterar arquivos automaticamente.

Comandos operacionais:

```bash
python tools/docker_projects.py discover --root ~/Documents
python tools/docker_projects.py status --root ~/Documents
python tools/docker_projects.py down --root ~/Documents
```

## Fluxo de uma tarefa

1. Cliente dita ou escreve o objetivo.
2. DevPilot registra transcript/prompt e avalia risco.
3. Ações sensíveis aguardam aprovação.
4. O worker cria uma branch exclusiva e chama Codex.
5. Testes, logs e resumo ficam associados à execução.
6. Push/PR podem ser adicionados como uma etapa separada e explicitamente aprovada.

## Próximas etapas para produção

- autenticação OIDC e organizações com RBAC;
- migrations Alembic e backups automatizados;
- GitHub App com webhooks e tokens de instalação;
- OpenAI Realtime/WebRTC e transcrição server-side;
- eventos ao vivo por SSE/WebSocket;
- runners efêmeros por tarefa e limites de custo;
- cobrança por workspace, assentos e minutos de execução;
- observabilidade OpenTelemetry, SLOs e alertas;
- análise de segurança e qualidade em PRs.

## Segurança

Nunca envie chaves ao frontend após o cadastro. Em produção, use um KMS/secret manager,
tokens curtos para GitHub Apps, runners sem privilégios e aprovação explícita para push,
merge, deploy, dependências e operações destrutivas.
