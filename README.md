# DevPilot — seu desenvolvedor

**Atualizado em: 23/08/2026**

DevPilot é uma plataforma leve de desenvolvimento assistido por IA que **analisa, orienta,
executa com controle e ensina usando o projeto real**. Ele organiza múltiplos projetos e
tarefas, aplica instruções `AGENTS.md`, controla configurações do Codex, executa trabalho em
branches isoladas, verifica riscos de segurança e registra cada decisão em uma trilha de
auditoria encadeada por hash.

## O que o MVP entrega

- dashboard responsivo/PWA para desktop e celular;
- projetos com URL Git, branch, `AGENTS.md` e perfil Codex;
- tarefas vindas do dashboard, voz ou API;
- fila persistente e worker independente;
- aprovação humana para ações de risco;
- executor Codex com `subprocess` sem shell e timeout;
- **DevPilot Mentor** com modos Explicar, Ensinar, Fazer comigo, Quiz e Executar;
- perfil educacional por usuário, projeto e competência;
- contexto de IA limitado e redigido, com snapshots por commit/contexto;
- **DevPilot Security** com scanner estático local para código, configuração, containers e CI/CD;
- achados de segurança com severidade, evidência redigida, impacto e remediação;
- correções de segurança somente por tarefa explícita e ainda sujeitas à aprovação;
- vault criptografado para múltiplos provedores de IA;
- auditoria de comandos, configuração, aprendizado, segurança, aprovação e execução;
- contabilização de tokens por usuário, projeto, tarefa, execução, provedor e modelo;
- Centro de Custos de IA com ledger financeiro versionado, cobertura de precificação e histórico;
- orçamento diário/mensal de IA com alerta e hard stop para evitar gasto adicional;
- política de hosts Git permitidos e isolamento de diretórios;
- Docker Compose com aplicação, worker e PostgreSQL;
- SQLite para desenvolvimento local sem infraestrutura adicional.

## Arquitetura

```text
PWA responsiva
   │ texto / voz / aprovação / ensino
FastAPI ── política ── auditoria hash-chain
   │          │                │
   │          ├── Mentor ──────┤
   │          │    │ contexto seguro / snapshot
   │          │    └── tarefa somente leitura
   │          │
   │          └── Security Engine ── scanner local / findings
   │
PostgreSQL/SQLite ── vault criptografado
   │
worker ── projeto isolado ── Codex CLI ── Git branch/PR
   │
ledger de IA ── preços versionados ── orçamento / hard stop
```

O MVP usa voz encadeada: reconhecimento no dispositivo, transcrição revisável, interpretação,
aprovação e execução. Isso mantém o comando auditável. Uma evolução natural é substituir a
captura pelo OpenAI Realtime via WebRTC, usando credenciais efêmeras emitidas pelo backend.

## Mentor e Segurança

O **DevPilot Mentor** usa o repositório real como material didático. Nos modos `explain`,
`teach`, `pair` e `quiz`, o sistema prepara um contexto limitado do projeto, exclui arquivos
sensíveis, redige padrões de segredo e cria uma tarefa em modo somente leitura. O modo
`execute` continua sendo desenvolvimento normal e sempre nasce aguardando aprovação.

O **DevPilot Security** executa uma varredura local e determinística, sem consumir tokens de
IA. A primeira versão verifica, entre outros pontos, arquivos sensíveis versionados, possíveis
segredos hard-coded, execução insegura de comandos, CORS amplo, debug, validação JWT,
permissões de GitHub Actions e Docker sem usuário não-root. Cada achado informa severidade,
impacto e remediação; criar uma correção exige confirmação explícita e a tarefa resultante ainda
fica sujeita à política de aprovação do DevPilot.

O scanner identifica manifests de dependências, mas não afirma vulnerabilidades de versão sem
uma fonte confiável de advisories. A integração com OSV/GitHub Advisory Database fica como
etapa separada; até lá a cobertura reporta explicitamente que a base de CVEs não está habilitada.

Detalhes de arquitetura, contratos, autorização, custos, rollback e operação estão em
[`docs/mentor-security.md`](docs/mentor-security.md).

## Custos de IA

O DevPilot persiste o consumo reportado pelos provedores e congela o custo calculado com a
versão de preço vigente no momento da contabilização. Dessa forma, uma alteração futura de
preço não modifica retroativamente o histórico financeiro. Operações externas que não retornam
metadados suficientes para uma precificação exata permanecem visíveis como `unpriced`, em vez
de receberem uma estimativa inventada.

O Super Admin pode definir orçamento diário e mensal. Com `hard stop` habilitado, o worker
verifica o orçamento antes da primeira execução e novamente antes de cada tentativa de
autocorreção. Chat, transcrição, TTS e sessões do Mentor que usam IA também respeitam o
bloqueio. A conversão para reais é apenas de exibição e pode ser configurada por
`DEVPILOT_USD_BRL_RATE`; com valor zero, o painel mantém somente o custo autoritativo em USD.

O scanner de segurança e a construção do snapshot são locais e não consomem tokens. O contexto
enviado a uma sessão do Mentor é limitado, em vez de reenviar o repositório inteiro.

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

1. Cliente dita, escreve ou inicia uma ação pelo Mentor/Security.
2. DevPilot registra a intenção e avalia risco.
3. Ações sensíveis aguardam aprovação.
4. O worker valida o orçamento de IA antes de consumir o provedor.
5. O worker executa em contexto isolado; análises somente leitura usam worktree descartável.
6. Tokens, custo, testes, logs, aprendizado e resumo ficam associados à execução/auditoria.
7. Push, merge e deploy permanecem etapas separadas e explicitamente aprovadas.

## Próximas etapas para produção

- autenticação OIDC e organizações com RBAC;
- migrations Alembic e backups automatizados;
- GitHub App com webhooks e tokens de instalação;
- integrar OSV/GitHub Advisory Database para CVEs de dependências com fonte verificável;
- transformar o Security Engine em gate opcional de PR/merge;
- OpenAI Realtime/WebRTC e transcrição server-side;
- eventos ao vivo por SSE/WebSocket;
- runners efêmeros por tarefa;
- cobrança por workspace, assentos e minutos de execução;
- observabilidade OpenTelemetry, SLOs e alertas;
- reconciliação periódica do ledger com faturamento dos provedores.

## Segurança

Nunca envie chaves ao frontend após o cadastro. Em produção, use um KMS/secret manager,
tokens curtos para GitHub Apps, runners sem privilégios e aprovação explícita para push,
merge, deploy, dependências e operações destrutivas.

O Mentor não deve transformar o banco em um espelho do código: snapshots persistem metadados
e contexto estrutural; trechos de arquivo alvo são reconstruídos para a sessão e não são
persistidos no snapshot. Arquivos reconhecidos como sensíveis não entram no contexto de IA.

`DEVPILOT_BOOTSTRAP_TOKEN` é uma credencial de inicialização, não uma segunda conta de
administrador. Use-a apenas no endpoint de bootstrap do primeiro usuário, mantenha-a fora
do frontend e faça rotação/remoção do segredo do ambiente após a configuração inicial.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

