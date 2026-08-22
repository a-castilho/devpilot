# DevPilot — seu desenvolvedor

**Atualizado em: 22/08/2026**

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
- contabilização de tokens por usuário, projeto, tarefa, execução, provedor e modelo;
- Centro de Custos de IA com ledger financeiro versionado, cobertura de precificação e histórico;
- orçamento diário/mensal de IA com alerta e hard stop para evitar gasto adicional;
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
   │
ledger de IA ── preços versionados ── orçamento / hard stop
```

O MVP usa voz encadeada: reconhecimento no dispositivo, transcrição revisável, interpretação,
aprovação e execução. Isso mantém o comando auditável. Uma evolução natural é substituir a
captura pelo OpenAI Realtime via WebRTC, usando credenciais efêmeras emitidas pelo backend.

## Custos de IA

O DevPilot persiste o consumo reportado pelos provedores e congela o custo calculado com a
versão de preço vigente no momento da contabilização. Dessa forma, uma alteração futura de
preço não modifica retroativamente o histórico financeiro. Operações externas que não retornam
metadados suficientes para uma precificação exata permanecem visíveis como `unpriced`, em vez
de receberem uma estimativa inventada.

O Super Admin pode definir orçamento diário e mensal. Com `hard stop` habilitado, o worker
verifica o orçamento antes da primeira execução e novamente antes de cada tentativa de
autocorreção. Chat, transcrição e TTS remotos também respeitam o bloqueio. A conversão para
reais é apenas de exibição e pode ser configurada por `DEVPILOT_USD_BRL_RATE`; com valor zero,
o painel mantém somente o custo autoritativo em USD.

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
4. O worker valida o orçamento de IA antes de consumir o provedor.
5. O worker cria uma branch exclusiva e chama Codex.
6. Tokens, custo, testes, logs e resumo ficam associados à execução.
7. Push/PR podem ser adicionados como uma etapa separada e explicitamente aprovada.

## Próximas etapas para produção

- autenticação OIDC e organizações com RBAC;
- migrations Alembic e backups automatizados;
- GitHub App com webhooks e tokens de instalação;
- OpenAI Realtime/WebRTC e transcrição server-side;
- eventos ao vivo por SSE/WebSocket;
- runners efêmeros por tarefa;
- cobrança por workspace, assentos e minutos de execução;
- observabilidade OpenTelemetry, SLOs e alertas;
- reconciliação periódica do ledger com faturamento dos provedores;
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

