# DevPilot — consultor de desenvolvimento com IA

**Atualizado em: 22/08/2026**

DevPilot é um consultor de desenvolvimento com IA acessível por dashboard, API ou voz.
Ele analisa projetos, identifica problemas e riscos, recomenda melhorias, propõe soluções,
acompanha a evolução técnica e, quando autorizado, executa mudanças em branches isoladas.
Cada decisão e ação fica registrada em uma trilha de auditoria encadeada por hash.

## Como o DevPilot atua

1. observa o estado técnico e reúne evidências;
2. diagnostica problemas, riscos e regressões;
3. apresenta recomendações compreensíveis e priorizadas;
4. propõe uma correção segura, testável e reversível;
5. solicita autorização quando a ação exigir escrita ou risco;
6. executa, valida e acompanha o resultado.

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

Abra `http://localhost:8080`. No primeiro acesso, use `DEVPILOT_BOOTSTRAP_TOKEN` somente
para criar o primeiro usuário `SUPER_ADMIN`. A API devolve um token de sessão e, a partir
desse momento, o acesso normal deve ser feito por e-mail e senha. O token de bootstrap não
é aceito como sessão administrativa em endpoints normais.

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

`DEVPILOT_BOOTSTRAP_TOKEN` é uma credencial de inicialização, não uma segunda conta de
administrador. Use-a apenas no endpoint de bootstrap do primeiro usuário, mantenha-a fora
do frontend e faça rotação/remoção do segredo do ambiente após a configuração inicial.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

